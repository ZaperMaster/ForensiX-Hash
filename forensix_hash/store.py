"""Registros guardados en disco y registro de cadena de custodia.

- records/<id>.json: un registro por evidencia (sellado).
- custody.jsonl: un evento por línea (hash creado, verificado, informe exportado).
  Cada evento incluye el hash del anterior, así que borrar, reordenar o editar
  una línea rompe la cadena y se detecta.
- custody.head.json: el último evento conocido. Borrar los eventos finales no
  rompe los enlaces de los que quedan, así que esto (y que cada registro tenga
  su evento de creación) es lo que delata ese recorte.

La carpeta es %LOCALAPPDATA%\\ForensiX Hash en Windows y ~/.local/share/forensix-hash
en Linux; se puede cambiar con la variable de entorno FORENSIX_HASH_HOME.
"""

import json
import os
import re
from pathlib import Path
from threading import Lock

from .record import canonical, compute_seal, now, seal, seal_ok, status
from .signing import sign_record

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
    """Ruta del registro; el id (32 hex) puede venir de la API o de un JSON importado."""

    if not _ID.match(record_id or ""):
        raise KeyError(record_id)
    folder = os.path.normpath(home() / "records")
    path = os.path.normpath(os.path.join(folder, f"{record_id}.json"))
    if not path.startswith(folder + os.sep):
        raise KeyError(record_id)
    return Path(path)


def save_record(record: dict) -> dict:
    seal(record)
    sign_record(record, home())
    return write_record(record)


def write_record(record: dict) -> dict:
    """Guarda el registro tal cual: al importar, conserva el sello y la firma de quien lo creó."""

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
        "imaged": bool(record.get("image")),
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


def _head_path() -> Path:
    return home() / "custody.head.json"


def _read_head() -> dict | None:
    try:
        head = json.loads(_head_path().read_text(encoding="utf-8"))
        return head if isinstance(head, dict) else {}
    except FileNotFoundError:
        return None
    except (OSError, ValueError):
        return {}


def _write_head(event: dict) -> None:
    temporary = _head_path().with_suffix(".tmp")
    temporary.write_text(json.dumps({"seq": event["seq"], "hash": event["hash"]}), encoding="utf-8")
    temporary.replace(_head_path())


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
        _write_head(event)
        return event


def _records_without_event(events: list[dict]) -> list[str]:
    """Registros firmados cuyo evento de creación ya no está en la cadena.

    Solo los firmados: los anteriores a la firma guardaban el registro antes que el
    evento, así que uno interrumpido puede no tenerlo sin que nadie haya tocado nada.
    """

    known = {e.get("record_id") for e in events if e.get("action") in ("created", "imported")}
    missing = []
    for path in (home() / "records").glob("*.json"):
        if path.stem in known:
            continue
        try:
            if "signature" in json.loads(path.read_text(encoding="utf-8")):
                missing.append(path.stem)
        except (OSError, ValueError):
            missing.append(path.stem)
    return missing


def check_custody(events: list[dict] | None = None) -> dict:
    """Comprueba la cadena: enlaces, ediciones y eventos finales borrados."""

    events = read_custody() if events is None else events
    previous = GENESIS
    for index, event in enumerate(events, start=1):
        if ("invalid" in event or event.get("seq") != index or event.get("prev") != previous
                or event.get("hash") != _event_hash(event)):
            return {"ok": False, "events": len(events), "broken_at": index, "reason": "edited"}
        previous = event["hash"]

    head = _read_head()
    if head is not None:
        seq = head.get("seq")
        if not isinstance(seq, int) or seq > len(events) or events[seq - 1].get("hash") != head.get("hash"):
            return {"ok": False, "events": len(events), "broken_at": len(events) + 1, "reason": "truncated"}
    if _records_without_event(events):
        return {"ok": False, "events": len(events), "broken_at": len(events) + 1, "reason": "truncated"}
    return {"ok": True, "events": len(events), "broken_at": None, "reason": None}


def record_custody(record_id: str) -> list[dict]:
    return [e for e in read_custody() if e.get("record_id") == record_id]
