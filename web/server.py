"""API local de ForensiX Hash (FastAPI) y la interfaz en /.

Solo escucha en 127.0.0.1. Como puede leer archivos y discos del equipo, toda la
API exige la cabecera X-ForensiX (una web ajena no puede enviarla sin permiso
CORS) y un Host local (evita ataques de DNS rebinding).
"""

import json
import os
import string
import subprocess
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from forensix_hash import APP_NAME, REPO_URL, __version__, devices, pdf, report, store, updater
from forensix_hash.hasher import ALGORITHMS, DEFAULT_ALGORITHMS
from forensix_hash.jobs import JobManager, error_message
from forensix_hash.record import CASE_FIELDS, seal_ok

STATIC_DIR = Path(__file__).parent / "static"
INDEX_FILE = STATIC_DIR / "index.html"
ALLOWED_HOSTS = {"127.0.0.1", "localhost", "[::1]", "testserver"}
API_HEADER = "x-forensix"

app = FastAPI(title=APP_NAME, description="Hashes forenses verificados", version=__version__,
              docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
jobs = JobManager()


def _host_name(header: str) -> str:
    """'127.0.0.1:8000' -> '127.0.0.1'; '[::1]:8000' -> '[::1]'."""

    if header.startswith("["):
        return header.split("]")[0] + "]"
    return header.rsplit(":", 1)[0]


@app.middleware("http")
async def local_only(request: Request, call_next):
    if _host_name(request.headers.get("host") or "") not in ALLOWED_HOSTS:
        return JSONResponse({"detail": "Host no permitido."}, status_code=403)
    if request.url.path.startswith("/api/") and request.headers.get(API_HEADER) != "1":
        return JSONResponse({"detail": "Falta la cabecera X-ForensiX."}, status_code=403)
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    if request.url.path.startswith("/static/"):
        # Tras una actualización, la interfaz nueva debe verse sin restos en caché.
        response.headers["Cache-Control"] = "no-cache"
    return response


# --- Modelos ------------------------------------------------------------------------

class CaseData(BaseModel):
    case_number: str = Field("", max_length=200)
    evidence_number: str = Field("", max_length=200)
    examiner: str = Field("", max_length=200)
    organization: str = Field("", max_length=200)
    description: str = Field("", max_length=2000)
    notes: str = Field("", max_length=2000)


class AcquireRequest(BaseModel):
    kind: str = Field(pattern="^(file|directory|disk)$")
    target: str = Field(min_length=1, max_length=4096)
    algorithms: list[str] = Field(default_factory=lambda: list(DEFAULT_ALGORITHMS), min_length=1)
    case: CaseData
    output: str | None = Field(None, max_length=4096)   # Carpeta del informe PDF
    lang: str = Field("es", pattern="^(es|en)$")


class VerifyRequest(BaseModel):
    examiner: str = Field("", max_length=200)
    target: str | None = Field(None, max_length=4096)
    notes: str = Field("", max_length=2000)
    output: str | None = Field(None, max_length=4096)
    lang: str = Field("es", pattern="^(es|en)$")


class OpenRequest(BaseModel):
    path: str = Field(min_length=1, max_length=4096)
    folder: bool = False


class ExportRequest(BaseModel):
    format: str = "pdf"
    lang: str = Field("es", pattern="^(es|en)$")
    folder: str | None = Field(None, max_length=4096)


def _bad_request(error: Exception) -> HTTPException:
    message = error_message(error) if isinstance(error, OSError) else str(error)
    status = 403 if isinstance(error, PermissionError) else 404 if isinstance(error, FileNotFoundError) else 400
    return HTTPException(status_code=status, detail=message)


def _record(record_id: str) -> dict:
    try:
        return store.load_record(record_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="El registro no existe.") from None


# --- Interfaz ------------------------------------------------------------------------

@app.get("/", include_in_schema=False)
def home():
    return FileResponse(INDEX_FILE, headers={"Cache-Control": "no-store"})


@app.get("/report/{record_id}", include_in_schema=False)
def report_page(record_id: str, lang: str = "es", print_dialog: int = Query(0, alias="print")):
    """Informe HTML para verlo o imprimirlo a PDF (?print=1 abre el diálogo de impresión)."""

    record = _record(record_id)
    html = report.to_html(record, store.record_custody(record_id), "en" if lang == "en" else "es")
    if print_dialog:
        html = html.replace("</body>", "<script>addEventListener('load',()=>print())</script></body>")
    return HTMLResponse(html, headers={"Cache-Control": "no-store"})


# --- Información y sistema de archivos -------------------------------------------------

@app.get("/api/info")
def info():
    return {
        "app": APP_NAME, "version": __version__, "repo": REPO_URL,
        "admin": devices.is_admin(), "os": os.name,
        "algorithms": [{"id": key, "name": name, "default": key in DEFAULT_ALGORITHMS}
                       for key, name in ALGORITHMS.items()],
        "case_fields": list(CASE_FIELDS),
        "home": str(store.home()),
        "reports_folder": str(pdf.default_folder()),
        "pdf_available": pdf.find_browser() is not None,
    }


@app.get("/api/update")
def check_update():
    """¿Hay una versión nueva publicada en GitHub? (Ajustes → Actualizaciones)."""

    try:
        return updater.check()
    except updater.UpdateError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@app.get("/api/disks")
def disks():
    return {"admin": devices.is_admin(), "disks": devices.list_devices()}


@app.get("/api/browse")
def browse(path: str = ""):
    """Contenido de una carpeta para elegir archivo o carpeta en la versión web."""

    if not path:
        if os.name == "nt":
            roots = [f"{letter}:\\" for letter in string.ascii_uppercase if os.path.exists(f"{letter}:\\")]
        else:
            roots = ["/"]
        return {"path": "", "parent": None, "entries": [{"name": r, "path": r, "dir": True} for r in roots]
                + [{"name": "~", "path": str(Path.home()), "dir": True}]}
    folder = Path(path).expanduser()
    try:
        folder = folder.resolve()
        entries = []
        with os.scandir(folder) as items:
            for item in items:
                try:
                    is_dir = item.is_dir(follow_symlinks=False)
                    size = None if is_dir else item.stat(follow_symlinks=False).st_size
                except OSError:
                    continue
                entries.append({"name": item.name, "path": item.path, "dir": is_dir, "size": size})
    except OSError as error:
        raise _bad_request(error) from error
    entries.sort(key=lambda e: (not e["dir"], e["name"].lower()))
    parent = str(folder.parent) if folder.parent != folder else ""
    return {"path": str(folder), "parent": parent, "entries": entries[:5000]}


# --- Operaciones -----------------------------------------------------------------------

@app.post("/api/jobs")
def start_acquisition(request: AcquireRequest):
    try:
        job = jobs.acquire(request.kind, request.target, request.algorithms, request.case.model_dump(),
                           request.output or None, request.lang)
    except (OSError, ValueError) as error:
        raise _bad_request(error) from error
    return job.snapshot()


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str):
    try:
        return jobs.get(job_id).snapshot()
    except KeyError:
        raise HTTPException(status_code=404, detail="La operación no existe.") from None


@app.delete("/api/jobs/{job_id}")
def cancel_job(job_id: str):
    try:
        return jobs.cancel(job_id).snapshot()
    except KeyError:
        raise HTTPException(status_code=404, detail="La operación no existe.") from None


# --- Registros -----------------------------------------------------------------------

@app.get("/api/records")
def records():
    return store.list_records()


@app.get("/api/records/{record_id}")
def get_record(record_id: str):
    record = _record(record_id)
    custody = store.record_custody(record_id)
    reports = [e["path"] for e in custody if e.get("format") == "pdf" and e.get("path")]
    return {"record": record, "summary": store.summary(record), "seal_ok": seal_ok(record),
            "custody": custody, "reports": [{"path": p, "exists": Path(p).exists()} for p in reports]}


@app.post("/api/records/{record_id}/pdf")
def record_pdf(record_id: str, request: ExportRequest):
    """Vuelve a crear el informe PDF del registro en una carpeta (por defecto, Documentos)."""

    record = _record(record_id)
    try:
        folder = pdf.check_destination(record, record["target"], request.folder or pdf.default_folder())
        return {"pdf": str(pdf.save_report(record, folder, request.lang))}
    except (OSError, ValueError, RuntimeError) as error:
        raise _bad_request(error) from error


def _known_reports() -> set[str]:
    return {os.path.normcase(e["path"]) for e in store.read_custody() if e.get("format") == "pdf" and e.get("path")}


@app.post("/api/open")
def open_report(request: OpenRequest):
    """Abre un informe PDF creado por la app, o su carpeta. Solo informes de la cadena de custodia."""

    if os.path.normcase(request.path) not in _known_reports():
        raise HTTPException(status_code=404, detail="Ese informe no lo ha creado ForensiX Hash.")
    path = Path(request.path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="El informe ya no está en esa carpeta.")
    if os.name != "nt":
        raise HTTPException(status_code=400, detail="Solo disponible en Windows.")
    if request.folder:
        subprocess.Popen(["explorer", "/select,", str(path)])
    else:
        os.startfile(str(path))  # Solo PDF creados por la app (comprobado arriba)
    return {"opened": str(path)}


@app.delete("/api/records/{record_id}")
def remove_record(record_id: str):
    record = _record(record_id)
    store.log_event("deleted", record)
    store.delete_record(record_id)
    return {"deleted": record_id}


@app.post("/api/records/{record_id}/verify")
def verify_record(record_id: str, request: VerifyRequest):
    _record(record_id)
    try:
        job = jobs.verify(record_id, request.examiner, request.target or None, request.notes,
                          request.output or None, request.lang)
    except (OSError, ValueError) as error:
        raise _bad_request(error) from error
    return job.snapshot()


@app.post("/api/records/{record_id}/export")
def export_record(record_id: str, request: ExportRequest):
    record = _record(record_id)
    if request.format == "pdf":
        # El PDF lo genera la ventana (app) o el navegador (web): aquí solo se anota.
        store.log_event("exported", record, format="pdf")
        return {"logged": True}
    if request.format not in report.EXPORTS:
        raise HTTPException(status_code=400, detail="Formato no soportado.")
    try:
        content = report.export(record, request.format, store.record_custody(record_id), request.lang)
    except ValueError as error:
        raise _bad_request(error) from error
    store.log_event("exported", record, format=request.format)
    mime = report.EXPORTS[request.format][0]
    return {"filename": report.filename(record, request.format), "mime": mime, "content": content}


@app.post("/api/import")
async def import_record(request: Request):
    """Importa un informe JSON de ForensiX Hash (por ejemplo, de otro equipo) para verificarlo."""

    body = await request.body()
    if len(body) > 200 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="El informe es demasiado grande.")
    try:
        record = json.loads(body)
        required = ("id", "kind", "target", "algorithms", "hashes", "case", "created")
        if not isinstance(record, dict) or record.get("format") != "forensix-hash/1" \
                or any(key not in record for key in required):
            raise ValueError
        store.summary({**record, "verifications": record.get("verifications") or []})
    except (ValueError, KeyError, TypeError, AttributeError):
        raise HTTPException(status_code=400, detail="No es un informe JSON de ForensiX Hash.") from None

    intact = seal_ok(record)
    try:
        existing = store.load_record(record["id"])
    except KeyError:
        existing = None
    if existing is None:
        if not intact:
            raise HTTPException(status_code=422,
                                detail="El informe ha sido modificado: su sello no coincide. No se importa.")
        store.save_record(record)
        store.log_event("imported", record)
    return {"id": record["id"], "seal_ok": intact, "already_present": existing is not None}


@app.get("/api/custody")
def custody():
    return {"check": store.check_custody(), "events": store.read_custody()[-500:]}
