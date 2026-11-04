"""Lectura y hash de las tres clases de evidencia: archivo, carpeta y disco.

Todo se abre en modo solo lectura. Las funciones devuelven diccionarios listos
para guardarse en el registro (JSON) y para compararse en la verificación.
"""

import os
import stat as stat_module
import unicodedata
from datetime import datetime
from pathlib import Path
from threading import Event

from . import devices
from .hasher import CHUNK_SIZE, MultiHasher, check_cancel, hashlib
from .progress import Progress


def iso_time(timestamp: float | None) -> str | None:
    if timestamp is None:
        return None
    return datetime.fromtimestamp(timestamp).astimezone().isoformat(timespec="seconds")


def file_times(info: os.stat_result) -> dict:
    """Marcas de tiempo MAC(B) del sistema de archivos."""

    created = getattr(info, "st_birthtime", None)
    if created is None and os.name == "nt":
        created = info.st_ctime
    return {
        "created": iso_time(created),
        "modified": iso_time(info.st_mtime),
        "accessed": iso_time(info.st_atime),
    }


def _read_into(handle, hasher: MultiHasher, progress: Progress | None, cancel: Event | None) -> int:
    total = 0
    while True:
        check_cancel(cancel)
        chunk = handle.read(CHUNK_SIZE)
        if not chunk:
            return total
        hasher.update(chunk)
        total += len(chunk)
        if progress:
            progress.add_bytes(len(chunk))


# --- Archivo -----------------------------------------------------------------

def describe_file(path: str | Path) -> dict:
    path = Path(path).resolve()
    info = path.stat()
    if not stat_module.S_ISREG(info.st_mode):
        raise ValueError(f"No es un archivo: {path}")
    return {
        "path": str(path),
        "name": path.name,
        "size": info.st_size,
        "times": file_times(info),
        "read_only": not os.access(path, os.W_OK),
    }


def hash_file(path, hasher: MultiHasher, progress: Progress | None = None,
              cancel: Event | None = None) -> dict:
    """Hash de un archivo. Avisa si cambió mientras se leía."""

    path = Path(path)
    before = path.stat()
    with open(path, "rb") as handle:
        size = _read_into(handle, hasher, progress, cancel)
    hashes = hasher.digest()
    after = path.stat()
    result = {"size": size, "hashes": hashes}
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns) or size != after.st_size:
        result["changed_while_reading"] = True
    return result


# --- Carpeta -----------------------------------------------------------------

def _relative(root: Path, path: Path) -> str:
    """Ruta relativa con '/' y Unicode normalizado, igual en Windows y Linux."""

    return unicodedata.normalize("NFC", path.relative_to(root).as_posix())


def _is_link(path: str) -> bool:
    return os.path.islink(path) or (hasattr(os.path, "isjunction") and os.path.isjunction(path))


def scan_directory(root: str | Path) -> dict:
    """Lista recursiva y ordenada de la carpeta, sin seguir enlaces."""

    root = Path(root).resolve()
    if not root.is_dir():
        raise ValueError(f"No es una carpeta: {root}")

    files, links, skipped = [], [], []

    def on_error(error: OSError) -> None:
        name = Path(error.filename) if error.filename else root
        skipped.append({"path": _relative(root, name) if name != root else ".",
                        "error": error.strerror or str(error)})

    for current, dirnames, filenames in os.walk(root, onerror=on_error, followlinks=False):
        current_path = Path(current)
        for name in list(dirnames):
            full = current_path / name
            if _is_link(str(full)):
                dirnames.remove(name)
                links.append({"path": _relative(root, full), "target": _link_target(full)})
        dirnames.sort()
        for name in filenames:
            full = current_path / name
            if _is_link(str(full)):
                links.append({"path": _relative(root, full), "target": _link_target(full)})
                continue
            try:
                info = full.stat()
            except OSError as error:
                skipped.append({"path": _relative(root, full), "error": error.strerror or str(error)})
                continue
            files.append({"path": _relative(root, full), "size": info.st_size,
                          "modified": iso_time(info.st_mtime)})

    files.sort(key=lambda item: item["path"])
    links.sort(key=lambda item: item["path"])
    skipped.sort(key=lambda item: item["path"])
    return {"root": str(root), "files": files, "links": links, "skipped": skipped}


def _link_target(path: Path) -> str:
    try:
        return os.readlink(path)
    except OSError:
        return ""


def manifest_text(files: list[dict], algorithm: str) -> str:
    """Manifiesto en formato `sha256sum` (hash, dos espacios, ruta), ordenado por ruta.

    El hash de la carpeta para cada algoritmo es el hash de este texto, así que
    se puede comprobar con cualquier herramienta: `sha256sum manifiesto.sha256`.
    """

    return "".join(f"{item['hashes'][algorithm]}  {item['path']}\n"
                   for item in files if "hashes" in item)


def manifest_hashes(files: list[dict], algorithms) -> dict[str, str]:
    return {a: hashlib.new(a, manifest_text(files, a).encode("utf-8")).hexdigest() for a in algorithms}


def hash_directory(root, hasher: MultiHasher, progress: Progress | None = None,
                   cancel: Event | None = None, phase: str = "hashing",
                   listing: dict | None = None) -> dict:
    """Hash de cada archivo de la carpeta y hash del conjunto (manifiesto)."""

    listing = listing or scan_directory(root)
    root_path = Path(listing["root"])
    total = sum(item["size"] for item in listing["files"])
    if progress:
        progress.start_phase(phase, total, len(listing["files"]))

    files = []
    for item in listing["files"]:
        check_cancel(cancel)
        if progress:
            progress.file_started(item["path"])
        entry = dict(item)
        try:
            entry.update(hash_file(root_path / item["path"], hasher, progress, cancel))
        except OSError as error:
            hasher.digest()  # Descarta lo leído y deja el hasher limpio
            entry["error"] = error.strerror or str(error)
        files.append(entry)
        if progress:
            progress.file_done()

    return {
        "root": listing["root"],
        "files": files,
        "links": listing["links"],
        "skipped": listing["skipped"],
        "totals": {
            "files": len(files),
            "hashed": sum(1 for f in files if "hashes" in f),
            "errors": sum(1 for f in files if "error" in f) + len(listing["skipped"]),
            "bytes": sum(f["size"] for f in files if "hashes" in f),
            "links": len(listing["links"]),
        },
        "hashes": manifest_hashes(files, hasher.algorithms),
    }


# --- Disco o imagen de disco --------------------------------------------------

def hash_device(path: str, hasher: MultiHasher, progress: Progress | None = None,
                cancel: Event | None = None, phase: str = "hashing", copy_to=None) -> dict:
    """Hash sector a sector de un disco físico, un volumen o una imagen (.dd, .raw, .iso, .E01…).

    Si un bloque no se puede leer se vuelve a intentar sector a sector; los
    sectores ilegibles se cuentan como ceros y se anotan, como hacen las
    herramientas de adquisición forense. Con `copy_to` (un archivo abierto) se
    escribe a la vez la imagen forense, exactamente con los datos que se hashean.
    """

    size, sector = devices.device_size(path)
    if progress:
        progress.start_phase(phase, size, 1)
        progress.file_started(path)

    bad_sectors: list[int] = []
    offset = 0
    with devices.open_device(path) as handle:
        while offset < size:
            check_cancel(cancel)
            length = min(CHUNK_SIZE, size - offset)
            try:
                handle.seek(offset)
                chunk = handle.read(length)
                if len(chunk) != length:
                    raise OSError(f"Lectura incompleta en el byte {offset}")
            except OSError:
                chunk = _read_sector_by_sector(handle, offset, length, sector, bad_sectors)
            hasher.update(chunk)
            if copy_to is not None:
                copy_to.write(chunk)
            offset += length
            if progress:
                progress.add_bytes(length)
        stored = handle.stored_hashes() if hasattr(handle, "stored_hashes") else None

    result = {"size": size, "sector_size": sector, "hashes": hasher.digest()}
    if stored is not None:
        result["ewf_stored"] = stored
    if bad_sectors:
        result["bad_sectors"] = {"count": len(bad_sectors), "first": bad_sectors[:100]}
    if progress:
        progress.file_done()
    return result


def _read_sector_by_sector(handle, offset: int, length: int, sector: int, bad: list[int]) -> bytes:
    parts = []
    for position in range(offset, offset + length, sector):
        size = min(sector, offset + length - position)
        try:
            handle.seek(position)
            data = handle.read(size)
            if len(data) != size:
                raise OSError()
        except OSError:
            data = b"\x00" * size
            bad.append(position // sector)
        parts.append(data)
    return b"".join(parts)
