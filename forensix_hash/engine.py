"""Adquisición (calcular los hashes) y verificación (volver a calcularlos y comparar).

Una adquisición siempre termina con una verificación automática: se lee la
evidencia por segunda vez y se comprueba que da los mismos hashes. Después se
puede verificar de nuevo cuando se quiera (por ejemplo, antes de un juicio), y
cada verificación queda anotada con quién la hizo y cuándo.
"""

import shutil
import uuid
from pathlib import Path
from threading import Event
from time import monotonic

from . import devices, paths, pdf, report, signing, store
from .hasher import Cancelled, MultiHasher, normalize_algorithms
from .progress import Progress
from .record import KINDS, clean_case, environment, now
from .sources import describe_file, hash_device, hash_directory, hash_file, scan_directory

FORMAT = "forensix-hash/1"
FAT_FILE_LIMIT = 4 * 1024 ** 3 - 1


def _measure(kind: str, target: str, algorithms, progress: Progress, cancel: Event | None,
             phase: str, copy_to=None) -> dict:
    """Lee la evidencia una vez y devuelve hashes, tamaño y detalles."""

    with MultiHasher(algorithms) as hasher:
        if kind == "file":
            size = Path(target).stat().st_size
            progress.start_phase(phase, size, 1)
            progress.file_started(Path(target).name)
            result = hash_file(target, hasher, progress, cancel)
            progress.file_done()
            return result
        if kind == "directory":
            progress.start_phase("scanning", 0)
            listing = scan_directory(target)
            return hash_directory(target, hasher, progress, cancel, phase=phase, listing=listing)
        return hash_device(target, hasher, progress, cancel, phase=phase, copy_to=copy_to)


def _resolve_target(kind: str, target: str) -> str:
    target = str(target or "").strip().strip('"')
    if not target:
        raise ValueError("Indica qué quieres hashear.")
    if kind not in KINDS:
        raise ValueError(f"Tipo de evidencia no válido: {kind}")
    if kind == "disk" and devices.is_raw_device(target):
        known = devices.known_device(target)  # Solo discos y volúmenes que existen en el equipo
        if not known:
            raise FileNotFoundError(f"No existe ese disco o volumen: {target}")
        return known
    path = Path(paths.local_path(target))
    if not path.exists():
        raise FileNotFoundError(f"No existe: {target}")
    if kind == "file" and not path.is_file():
        raise ValueError("La ruta no es un archivo.")
    if kind == "directory" and not path.is_dir():
        raise ValueError("La ruta no es una carpeta.")
    if kind == "disk" and not path.is_file():
        raise ValueError("Elige un disco de la lista o una imagen de disco (.dd, .raw, .img, .iso…).")
    return str(path.resolve())


def _source_info(kind: str, target: str) -> dict:
    if kind == "file":
        return describe_file(target)
    if kind == "directory":
        return {"path": target, "name": Path(target).name or target}
    return devices.describe_device(target)


def _label(kind: str, source: dict, target: str) -> str:
    if kind == "disk" and source.get("kind") == "disk":
        return f"{source.get('model') or 'Disco'} ({target})"
    if kind == "disk" and source.get("kind") == "volume":
        return f"{source.get('letter')} {source.get('label') or ''} ({source.get('filesystem') or ''})".strip()
    return source.get("name") or target


def _details(kind: str, measured: dict) -> dict:
    if kind == "directory":
        return {k: measured[k] for k in ("files", "links", "skipped", "totals")}
    details = {}
    for key in ("sector_size", "bad_sectors", "changed_while_reading"):
        if key in measured:
            details[key] = measured[key]
    if "ewf_stored" in measured:
        stored = measured["ewf_stored"]
        common = [a for a in stored if a in measured["hashes"]]
        details["ewf"] = {"stored": stored,
                          "match": all(stored[a] == measured["hashes"][a] for a in common) if common else None}
    return details


def _fingerprint() -> str:
    """Huella de quien actúa. Va dentro del contenido sellado: si otro equipo verifica y
    vuelve a firmar el registro, sigue constando la clave que lo creó."""

    return signing.identity(store.home())["fingerprint"]


def _size(kind: str, measured: dict) -> int:
    return measured["totals"]["bytes"] if kind == "directory" else measured["size"]


def check_image_destination(kind: str, target: str, folder) -> Path:
    """Comprueba que la imagen cabe en la carpeta y no va dentro de la evidencia."""

    if kind != "disk":
        raise ValueError("Solo se puede crear una imagen forense de un disco.")
    resolved = pdf.check_destination(kind, target, folder)
    resolved.mkdir(parents=True, exist_ok=True)
    size = devices.device_size(target)[0]
    if shutil.disk_usage(resolved).free < size:
        raise ValueError("No hay espacio suficiente en esa carpeta para la imagen.")
    if devices.filesystem_of(resolved).upper().startswith("FAT") and size > FAT_FILE_LIMIT:
        raise ValueError("Esa unidad es FAT32 y no admite archivos de más de 4 GB: elige otra para la imagen.")
    return resolved


def _write_image(kind, target, algorithms, progress, cancel, partial: Path) -> dict:
    """Primera lectura: hashes e imagen a la vez, con los mismos datos."""

    try:
        with open(partial, "wb") as image:
            return _measure(kind, target, algorithms, progress, cancel, "hashing", copy_to=image)
    except BaseException:
        partial.unlink(missing_ok=True)
        raise


def _verify_image(record: dict, progress: Progress, cancel: Event | None) -> None:
    """Lee la imagen creada y comprueba que da los mismos hashes que la evidencia."""

    image = record["image"]
    measured = _measure("disk", image["path"], record["algorithms"], progress, cancel, "verifying_image")
    same = measured["hashes"] == record["hashes"] and measured["size"] == record["size"]
    image.update(hashes=measured["hashes"], result="verified" if same else "mismatch", verified=now())


def acquire(kind: str, target: str, algorithms=None, case: dict | None = None,
            progress: Progress | None = None, cancel: Event | None = None,
            save: bool = True, image_folder=None) -> dict:
    """Calcula los hashes, los verifica con una segunda lectura y guarda el registro.

    Con `image_folder` crea además la imagen forense .dd durante esa primera lectura.
    """

    progress = progress or Progress()
    algorithms = normalize_algorithms(algorithms)
    case = clean_case(case)
    target = _resolve_target(kind, target)
    source = _source_info(kind, target)
    record_id = uuid.uuid4().hex

    started, clock = now(), monotonic()
    if image_folder:
        folder = check_image_destination(kind, target, image_folder)
        partial = folder / f"{record_id}.dd.partial"
        measured = _write_image(kind, target, algorithms, progress, cancel, partial)
    else:
        partial = None
        measured = _measure(kind, target, algorithms, progress, cancel, "hashing")
    record = {
        "format": FORMAT,
        "id": record_id,
        "kind": kind,
        "target": target,
        "label": _label(kind, source, target),
        "algorithms": list(algorithms),
        "case": case,
        "environment": {**environment(), "fingerprint": _fingerprint()},
        "source": source,
        "created": {"started": started, "finished": now(), "duration": round(monotonic() - clock, 2)},
        "hashes": measured["hashes"],
        "size": _size(kind, measured),
        "details": _details(kind, measured),
        "verifications": [],
    }

    if source.get("system"):
        record["details"]["live_system"] = True  # Windows escribe en él mientras se lee

    image_path = None
    if partial:
        image_path = partial.with_name(report.filename(record, "dd"))
        partial.replace(image_path)
        record["image"] = {"path": str(image_path), "format": "raw (dd)", "size": image_path.stat().st_size}
    try:
        verify(record, examiner=case["examiner"], progress=progress, cancel=cancel,
               automatic=True, save=False)
        if image_path:
            _verify_image(record, progress, cancel)
    except Cancelled:
        if image_path:
            image_path.unlink(missing_ok=True)
        raise

    if save:
        # Primero la custodia: si la app se cierra en medio, no queda un registro sin su evento.
        store.log_event("created", record, hashes=record["hashes"])
        store.log_event("verified", record, result=record["verifications"][-1]["result"],
                        automatic=True)
        store.save_record(record)
    progress.start_phase("done", 0)
    return record


def verify(record: dict, examiner: str = "", target: str | None = None,
           progress: Progress | None = None, cancel: Event | None = None,
           automatic: bool = False, save: bool = True, notes: str = "") -> dict:
    """Vuelve a leer la evidencia (o una copia en `target`) y compara los hashes.

    Añade la verificación al registro y la devuelve. Si se cancela, no se anota.
    """

    progress = progress or Progress()
    kind = record["kind"]
    examiner = (examiner or "").strip() or record["case"].get("examiner", "")
    checked = record["target"] if not target else _resolve_target(kind, target)

    started, clock = now(), monotonic()
    entry = {
        "number": len(record.get("verifications", [])) + 1,
        "automatic": automatic,
        "examiner": examiner[:200],
        "notes": (notes or "").strip()[:2000],
        "target": checked,
        "host": environment()["host"],
        "fingerprint": _fingerprint(),
        "started": started,
    }
    try:
        measured = _measure(kind, checked, record["algorithms"], progress, cancel, "verifying")
    except Cancelled:
        raise
    except OSError as error:
        entry.update(result="error", error=error.strerror or str(error))
    else:
        entry["hashes"] = measured["hashes"]
        entry["size"] = _size(kind, measured)
        differences = _differences(record, measured)
        if differences:
            entry["differences"] = differences
        same = measured["hashes"] == record["hashes"] and entry["size"] == record["size"]
        entry["result"] = "verified" if same and not differences else "mismatch"
    entry["finished"] = now()
    entry["duration"] = round(monotonic() - clock, 2)

    record.setdefault("verifications", []).append(entry)
    if save:
        store.log_event("verified", record, examiner=examiner, result=entry["result"],
                        automatic=automatic, checked_target=checked)
        store.save_record(record)
    return entry


def _differences(record: dict, measured: dict) -> dict:
    """Qué ha cambiado en una carpeta: archivos añadidos, eliminados y modificados."""

    if record["kind"] != "directory":
        return {}
    before = {f["path"]: f for f in record["details"]["files"]}
    after = {f["path"]: f for f in measured["files"]}
    modified = [path for path in sorted(before.keys() & after.keys())
                if before[path].get("hashes") != after[path].get("hashes")
                or before[path].get("error") != after[path].get("error")]
    differences = {
        "added": sorted(after.keys() - before.keys()),
        "removed": sorted(before.keys() - after.keys()),
        "modified": modified,
    }
    return {k: v[:1000] for k, v in differences.items() if v}
