"""Registros guardados en disco y registro de cadena de custodia.

- records/<id>.json: un registro por evidencia (sellado).
- custody.jsonl: un evento por línea (hash creado, verificado, informe exportado).
  Cada evento incluye el hash del anterior, así que borrar, reordenar o editar
  una línea rompe la cadena y se detecta.

La carpeta es %LOCALAPPDATA%\\ForensiX Hash en Windows y ~/.local/share/forensix-hash
en Linux; se puede cambiar con la variable de entorno FORENSIX_HASH_HOME.
"""

import json
import os
import re
from pathlib import Path
from threading import Lock

from .record import canonical, compute_seal, now, seal, seal_ok, status

_ID = re.compile(r"^[0-9a-f]{32}$")
_lock = Lock()
GENESIS = "0" * 64


def home() -> Path:
    custom = os.environ.get("FORENSIX_HASH_HOME")
    if custom:
        base = Path(custom)
    elif os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "ForensiX Hash"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "forensix-hash"
    (base / "records").mkdir(parents=True, exist_ok=True)
    return base


def _record_path(record_id: str) -> Path:
    if not _ID.match(record_id or ""):
        raise KeyError(record_id)
    return home() / "records" / f"{record_id}.json"


def save_record(record: dict) -> dict:
    seal(record)
    path = _record_path(record["id"])
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
    temporary.replace(path)
    return record


def load_record(record_id: str) -> dict:
    path = _record_path(record_id)
    if not path.exists():
        raise KeyError(record_id)
    return json.loads(path.read_text(encoding="utf-8"))


def delete_record(record_id: str) -> None:
    _record_path(record_id).unlink(missing_ok=True)


def summary(record: dict) -> dict:
    created = record.get("created") or {}
    verifications = record.get("verifications") or []
    return {
        "id": record["id"],
        "kind": record["kind"],
        "target": record["target"],
        "label": record.get("label") or record["target"],
        "case_number": record["case"].get("case_number", ""),
        "evidence_number": record["case"].get("evidence_number", ""),
        "examiner": record["case"].get("examiner", ""),
        "algorithms": record["algorithms"],
        "hashes": record["hashes"],
        "size": record.get("size", 0),
        "created": created.get("finished") or created.get("started"),
        "last_verified": verifications[-1]["finished"] if verifications else None,
        "verifications": len(verifications),
        "status": status(record),
        "seal_ok": seal_ok(record),
    }


def list_records() -> list[dict]:
    items = []
    for path in (home() / "records").glob("*.json"):
        try:
            items.append(summary(json.loads(path.read_text(encoding="utf-8"))))
        except (OSError, ValueError, KeyError):
            continue
    return sorted(items, key=lambda item: item["created"] or "", reverse=True)


# --- Cadena de custodia ------------------------------------------------------------

def _custody_path() -> Path:
    return home() / "custody.jsonl"


def _event_hash(event: dict) -> str:
    import hashlib

    return hashlib.sha256(canonical({k: v for k, v in event.items() if k != "hash"})).hexdigest()


def read_custody() -> list[dict]:
    path = _custody_path()
    if not path.exists():
        return []
    events = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                events.append(json.loads(line))
            except ValueError:
                events.append({"invalid": line})
    return events


def log_event(action: str, record: dict, **details) -> dict:
    """Añade un evento a la cadena de custodia."""

    with _lock:
        events = read_custody()
        previous = events[-1].get("hash", GENESIS) if events else GENESIS
        event = {
            "seq": len(events) + 1,
            "time": now(),
            "action": action,
            "record_id": record["id"],
            "kind": record["kind"],
            "target": record["target"],
            "case_number": record["case"].get("case_number", ""),
            "evidence_number": record["case"].get("evidence_number", ""),
            "examiner": details.pop("examiner", None) or record["case"].get("examiner", ""),
            "record_seal": compute_seal(record),
            **details,
            "prev": previous,
        }
        event["hash"] = _event_hash(event)
        with _custody_path().open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")
        return event


def check_custody(events: list[dict] | None = None) -> dict:
    """Comprueba la cadena: cada evento enlaza con el anterior y no se ha editado."""

    events = read_custody() if events is None else events
    previous = GENESIS
    for index, event in enumerate(events, start=1):
        if ("invalid" in event or event.get("seq") != index or event.get("prev") != previous
                or event.get("hash") != _event_hash(event)):
            return {"ok": False, "events": len(events), "broken_at": index}
        previous = event["hash"]
    return {"ok": True, "events": len(events), "broken_at": None}


def record_custody(record_id: str) -> list[dict]:
    return [e for e in read_custody() if e.get("record_id") == record_id]
