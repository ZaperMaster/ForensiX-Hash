"""Registro de una evidencia: datos del caso, hashes, cronología y verificaciones.

Cada registro lleva un sello: el SHA-256 de su contenido en JSON canónico. Si
alguien cambia un hash, una fecha o el nombre del examinador en el JSON, el
sello deja de coincidir y la app lo marca como modificado.
"""

import getpass
import hashlib
import json
import platform
import socket
from datetime import datetime

from . import APP_NAME, __version__
from .hasher import ALGORITHMS

CASE_FIELDS = ("case_number", "evidence_number", "examiner", "organization", "description", "notes")
REQUIRED_CASE_FIELDS = ("examiner",)
KINDS = ("file", "directory", "disk")


def now() -> str:
    """Fecha y hora local con zona horaria (ISO 8601), p. ej. 2026-11-03T12:30:05+01:00."""

    return datetime.now().astimezone().isoformat(timespec="seconds")


def clean_case(case: dict | None) -> dict:
    case = case or {}
    cleaned = {name: str(case.get(name) or "").strip()[:2000] for name in CASE_FIELDS}
    missing = [name for name in REQUIRED_CASE_FIELDS if not cleaned[name]]
    if missing:
        raise ValueError("Indica quién realiza el hash (examinador).")
    return cleaned


def environment() -> dict:
    from .devices import is_admin

    return {
        "tool": APP_NAME,
        "version": __version__,
        "host": socket.gethostname(),
        "user": _user(),
        "os": f"{platform.system()} {platform.release()} ({platform.version()})",
        "python": platform.python_version(),
        "admin": is_admin(),
    }


def _user() -> str:
    try:
        return getpass.getuser()
    except Exception:
        return ""


def canonical(data) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def compute_seal(record: dict) -> str:
    return hashlib.sha256(canonical({k: v for k, v in record.items() if k != "seal"})).hexdigest()


def seal(record: dict) -> dict:
    record["seal"] = {"algorithm": "sha256", "value": compute_seal(record)}
    return record


def seal_ok(record: dict) -> bool:
    stored = (record.get("seal") or {}).get("value")
    return bool(stored) and stored == compute_seal(record)


def algorithm_names(algorithms) -> list[str]:
    return [ALGORITHMS[a] for a in algorithms]


def status(record: dict) -> str:
    """verified | mismatch | error | pending, según la última verificación."""

    verifications = record.get("verifications") or []
    if not verifications:
        return "pending"
    return verifications[-1]["result"]
