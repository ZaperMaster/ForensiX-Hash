"""Actualizaciones automáticas firmadas (como en Lumen).

1. Al abrir la app se consulta la última Release de GitHub.
2. Si es más nueva, se descargan ForensiX-Hash.exe, SHA256SUMS.txt y SHA256SUMS.txt.sig.
3. La firma Ed25519 de SHA256SUMS.txt se comprueba con la clave pública de abajo
   (la privada solo la tiene el autor) y el SHA-256 del .exe debe coincidir.
4. Solo entonces se sustituye el .exe y se vuelve a abrir la app.

Nada se instala sin una firma válida.
"""

import base64
import hashlib
import json
import os
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

from . import REPO_URL, __version__

PUBLIC_KEY = "8ILjOOnhRISU44A8YX3efY7A1TW2d3i4z+WBS1tjzMo="
ASSET = "ForensiX-Hash.exe"
SUMS = "SHA256SUMS.txt"
SIGNATURE = "SHA256SUMS.txt.sig"
API = REPO_URL.replace("https://github.com/", "https://api.github.com/repos/") + "/releases/latest"
TIMEOUT = 20


class UpdateError(Exception):
    pass


def parse_version(text: str) -> tuple[int, ...]:
    digits = text.strip().lstrip("vV").split("-")[0]
    try:
        return tuple(int(part) for part in digits.split("."))
    except ValueError:
        return (0,)


def _get(url: str, limit: int = 300 * 1024 * 1024) -> bytes:
    if not url.startswith("https://"):
        raise UpdateError("Solo se descargan actualizaciones por HTTPS.")
    request = urllib.request.Request(url, headers={"User-Agent": f"ForensiX-Hash/{__version__}",
                                                   "Accept": "application/vnd.github+json"})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:  # noqa: S310 (solo https)
            data = response.read(limit + 1)
    except OSError as error:
        raise UpdateError(f"No se pudo conectar con GitHub: {error}") from error
    if len(data) > limit:
        raise UpdateError("La descarga es demasiado grande.")
    return data


def check(fetch=None) -> dict:
    """Información de la última versión publicada y si es más nueva que esta."""

    fetch = fetch or _get
    try:
        release = json.loads(fetch(API, 2 * 1024 * 1024))
    except ValueError as error:
        raise UpdateError("Respuesta de GitHub no válida.") from error
    latest = release.get("tag_name", "")
    assets = {a["name"]: a["browser_download_url"] for a in release.get("assets", [])}
    return {
        "current": __version__,
        "latest": latest.lstrip("v"),
        "available": parse_version(latest) > parse_version(__version__) and all(
            name in assets for name in (ASSET, SUMS, SIGNATURE)),
        "notes_url": release.get("html_url", REPO_URL + "/releases"),
        "assets": assets,
        "can_install": can_install(),
    }


def verify_signature(sums: bytes, signature: bytes, public_key: str | None = None) -> None:
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    try:
        key = Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key or PUBLIC_KEY))
        key.verify(base64.b64decode(signature.strip()), sums)
    except (InvalidSignature, ValueError) as error:
        raise UpdateError("La firma de la actualización no es válida. No se instala.") from error


def expected_hash(sums: bytes, name: str = ASSET) -> str:
    for line in sums.decode("utf-8", "replace").splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1].lstrip("*") == name:
            return parts[0].lower()
    raise UpdateError(f"{SUMS} no incluye {name}.")


def download_verified(info: dict, folder: Path, fetch=None, public_key: str | None = None) -> Path:
    """Descarga el .exe nuevo junto al actual y lo devuelve solo si la firma y el hash son correctos."""

    fetch = fetch or _get
    assets = info["assets"]
    sums = fetch(assets[SUMS], 1024 * 1024)
    verify_signature(sums, fetch(assets[SIGNATURE], 4096), public_key)
    executable = fetch(assets[ASSET])
    if hashlib.sha256(executable).hexdigest() != expected_hash(sums):
        raise UpdateError("El archivo descargado no coincide con su hash firmado. No se instala.")
    target = folder / f"{ASSET}.new"
    target.write_bytes(executable)
    return target


def can_install() -> bool:
    """Solo el .exe (no el código fuente) se puede sustituir a sí mismo, y si su carpeta es escribible."""

    return bool(getattr(sys, "frozen", False)) and os.access(Path(sys.executable).parent, os.W_OK)


def install(info: dict) -> None:
    """Sustituye el .exe en ejecución por el nuevo y lo abre. Windows permite renombrar un .exe abierto."""

    if not can_install():
        raise UpdateError("Esta copia no se puede actualizar sola: descarga la versión nueva desde GitHub.")
    current = Path(sys.executable)
    new = download_verified(info, current.parent)
    old = current.with_suffix(".exe.old")
    old.unlink(missing_ok=True)
    current.rename(old)
    try:
        new.rename(current)
    except OSError:
        old.rename(current)
        raise
    subprocess.Popen([str(current)], close_fds=True)


def cleanup() -> None:
    """Borra el .exe anterior que deja una actualización (al arrancar la versión nueva)."""

    if not getattr(sys, "frozen", False):
        return
    leftovers = [Path(sys.executable).with_suffix(".exe.old"), Path(sys.executable + ".new")]

    def remove() -> None:
        # La versión anterior puede tardar unos segundos en cerrarse y soltar su .exe.
        for _ in range(30):
            for leftover in leftovers:
                try:
                    leftover.unlink(missing_ok=True)
                except OSError:
                    pass
            if not any(leftover.exists() for leftover in leftovers):
                return
            time.sleep(1)

    threading.Thread(target=remove, daemon=True, name="limpiar-actualizacion").start()
