"""Progreso de una operación: bytes, archivos, fase, velocidad y tiempo restante."""

from dataclasses import dataclass, field
from threading import Lock
from time import monotonic

FILE_COST = 256 * 1024


@dataclass
class Progress:
    phase: str = "preparing"   # preparing | hashing | verifying | done
    bytes_total: int = 0       # De la fase actual
    bytes_done: int = 0
    files_total: int = 0
    files_done: int = 0
    current: str = ""
    _phase_started: float = field(default_factory=monotonic)
    _lock: Lock = field(default_factory=Lock, repr=False)

    def start_phase(self, phase: str, bytes_total: int, files_total: int = 0) -> None:
        with self._lock:
            self.phase = phase
            self.bytes_total = bytes_total
            self.bytes_done = 0
            self.files_total = files_total
            self.files_done = 0
            self.current = ""
            self._phase_started = monotonic()

    def add_bytes(self, count: int) -> None:
        with self._lock:
            self.bytes_done += count

    def file_started(self, name: str) -> None:
        with self._lock:
            self.current = name

    def file_done(self) -> None:
        with self._lock:
            self.files_done += 1

    def snapshot(self) -> dict:
        with self._lock:
            elapsed = max(monotonic() - self._phase_started, 1e-6)
            # Abrir cada archivo cuesta lo mismo que leer FILE_COST bytes: así el
            # porcentaje y el tiempo restante no engañan con miles de archivos pequeños.
            per_file = FILE_COST if self.files_total > 1 else 0
            total = self.bytes_total + self.files_total * per_file
            done = min(self.bytes_done + self.files_done * per_file, total)
            rate = done / elapsed
            return {
                "phase": self.phase,
                "bytes_total": self.bytes_total,
                "bytes_done": self.bytes_done,
                "files_total": self.files_total,
                "files_done": self.files_done,
                "current": self.current,
                "percent": round(100 * done / total, 1) if total else 0.0,
                "speed": round(self.bytes_done / elapsed),
                "elapsed": round(elapsed, 1),
                "eta": round((total - done) / rate) if rate > 0 and done else None,
            }
