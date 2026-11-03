"""Operaciones en segundo plano con progreso y cancelación (para la web y la app)."""

import uuid
from dataclasses import dataclass, field
from threading import Event, Lock, Thread

import subprocess

from . import engine, pdf, store
from .hasher import Cancelled
from .progress import Progress


def error_message(error: OSError) -> str:
    if error.filename and error.strerror:
        return f"{error.strerror}: {error.filename}"
    return error.strerror or str(error)


@dataclass
class Job:
    id: str
    action: str                  # acquire | verify
    title: str
    progress: Progress = field(default_factory=Progress)
    cancel: Event = field(default_factory=Event)
    state: str = "running"       # running | done | error | cancelled
    record_id: str | None = None
    result: str | None = None    # verified | mismatch | error
    error: str | None = None
    pdf: str | None = None       # Informe PDF guardado
    pdf_error: str | None = None

    def snapshot(self) -> dict:
        return {
            "id": self.id, "action": self.action, "title": self.title, "state": self.state,
            "record_id": self.record_id, "result": self.result, "error": self.error,
            "pdf": self.pdf, "pdf_error": self.pdf_error, "progress": self.progress.snapshot(),
        }

    def save_pdf(self, record: dict, folder, lang: str, suffix: str = "") -> None:
        """El informe PDF es el comprobante: si falla, el hash sigue guardado y se avisa."""

        if not folder:
            return
        self.progress.start_phase("report", 0)
        try:
            self.pdf = str(pdf.save_report(record, folder, lang, suffix))
        except (OSError, RuntimeError, subprocess.SubprocessError) as error:
            self.pdf_error = str(error)


class JobManager:
    def __init__(self):
        self._jobs: dict[str, Job] = {}
        self._lock = Lock()

    def _start(self, action: str, title: str, work) -> Job:
        job = Job(id=uuid.uuid4().hex, action=action, title=title)

        def run():
            try:
                record, result = work(job)
                job.record_id, job.result, job.state = record["id"], result, "done"
            except Cancelled:
                job.state = "cancelled"
            except OSError as error:
                job.state, job.error = "error", error_message(error)
            except (ValueError, KeyError) as error:
                job.state, job.error = "error", str(error)
            except Exception as error:  # Cualquier fallo se muestra en la interfaz
                job.state, job.error = "error", f"{type(error).__name__}: {error}"

        with self._lock:
            self._jobs[job.id] = job
        Thread(target=run, daemon=True, name=f"job-{job.id[:8]}").start()
        return job

    def acquire(self, kind: str, target: str, algorithms, case: dict, output: str | None = None,
                lang: str = "es") -> Job:
        # Errores de datos (sin examinador, ruta inexistente, informe dentro de la evidencia...)
        # se devuelven al momento.
        from .record import clean_case

        clean_case(case)
        resolved = engine._resolve_target(kind, target)
        folder = pdf.check_destination(kind, resolved, output) if output else None

        def work(job: Job):
            record = engine.acquire(kind, target, algorithms, case, job.progress, job.cancel)
            job.save_pdf(record, folder, lang)
            return record, record["verifications"][-1]["result"]

        return self._start("acquire", target, work)

    def verify(self, record_id: str, examiner: str, target: str | None = None, notes: str = "",
               output: str | None = None, lang: str = "es") -> Job:
        record = store.load_record(record_id)
        checked = engine._resolve_target(record["kind"], target) if target else record["target"]
        folder = pdf.check_destination(record, checked, output) if output else None

        def work(job: Job):
            entry = engine.verify(record, examiner=examiner, target=target, progress=job.progress,
                                  cancel=job.cancel, notes=notes)
            job.save_pdf(record, folder, lang, suffix=f"verificacion-{entry['number']}")
            return record, entry["result"]

        return self._start("verify", record["label"], work)

    def get(self, job_id: str) -> Job:
        with self._lock:
            return self._jobs[job_id]

    def cancel(self, job_id: str) -> Job:
        job = self.get(job_id)
        job.cancel.set()
        return job

    def running(self) -> list[Job]:
        with self._lock:
            return [job for job in self._jobs.values() if job.state == "running"]
