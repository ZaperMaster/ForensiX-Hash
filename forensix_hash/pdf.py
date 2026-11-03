"""Informe PDF: el HTML del informe impreso a PDF con Microsoft Edge (o Chrome) sin ventana.

Edge viene con Windows 10 y 11, así que el PDF se genera igual desde la app, la
web o la línea de comandos, sin dependencias extra.
"""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from . import devices, paths, report, store

TIMEOUT = 120
_CANDIDATES = [
    r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe",
    r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe",
    r"%ProgramFiles%\Google\Chrome\Application\chrome.exe",
    r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe",
    r"%LocalAppData%\Google\Chrome\Application\chrome.exe",
]


def find_browser() -> str | None:
    custom = os.environ.get("FORENSIX_HASH_BROWSER")
    if custom and Path(custom).exists():
        return custom
    for candidate in _CANDIDATES:
        path = Path(os.path.expandvars(candidate))
        if path.exists():
            return str(path)
    for name in ("msedge", "microsoft-edge", "google-chrome", "chromium", "chromium-browser"):
        found = shutil.which(name)
        if found:
            return found
    return None


def html_to_pdf(html: str, target: Path) -> Path:
    browser = find_browser()
    if not browser:
        raise RuntimeError("No se encontró Microsoft Edge ni Chrome para crear el PDF.")
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="forensix-pdf-") as work:
        source = Path(work) / "informe.html"
        source.write_text(html, encoding="utf-8")
        temporary = Path(work) / "informe.pdf"
        # En Linux (p. ej. Ubuntu 24) el sandbox de Chrome no arranca si los user namespaces
        # están restringidos. Solo se imprime el HTML del propio informe, generado aquí.
        sandbox = ["--no-sandbox"] if sys.platform.startswith("linux") else []
        subprocess.run(
            [browser, "--headless", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
             "--disable-extensions", *sandbox, f"--user-data-dir={Path(work) / 'perfil'}", "--no-pdf-header-footer",
             f"--print-to-pdf={temporary}", source.as_uri()],
            capture_output=True, timeout=TIMEOUT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if not temporary.exists() or temporary.stat().st_size == 0:
            raise RuntimeError("No se pudo crear el PDF del informe.")
        shutil.move(str(temporary), target)
    return target


def default_folder() -> Path:
    """Documentos\\ForensiX Hash (o ~/ForensiX Hash)."""

    documents = Path.home() / "Documents"
    return (documents if documents.exists() else Path.home()) / "ForensiX Hash"


def check_destination(record_or_kind, target: str, folder: str | Path) -> Path:
    """Comprueba que el informe no se guarda dentro de la evidencia (la modificaría)."""

    kind = record_or_kind["kind"] if isinstance(record_or_kind, dict) else record_or_kind
    if not str(folder or "").strip():
        raise ValueError("Elige dónde guardar el informe.")
    resolved = Path(paths.local_path(str(folder))).resolve()  # Solo unidades locales
    if kind == "directory":
        evidence = Path(target).resolve()
        if resolved == evidence or evidence in resolved.parents:
            raise ValueError("El informe no se puede guardar dentro de la carpeta que se hashea: la modificaría.")
    if kind == "disk" and devices.is_raw_device(target):
        letters = devices.letters_of(target)
        drive = resolved.drive.rstrip(":\\").upper()
        if drive and drive in letters:
            raise ValueError("El informe no se puede guardar en el disco que se hashea: lo modificaría.")
    return resolved


def save_report(record: dict, folder: str | Path, lang: str = "es", suffix: str = "") -> Path:
    """Crea el PDF del registro en `folder` y lo anota en la cadena de custodia."""

    name = report.filename(record, "pdf")
    if suffix:
        name = name[:-4] + f"_{suffix}.pdf"
    target = Path(folder) / name
    html = report.to_html(record, store.record_custody(record["id"]), lang)
    html_to_pdf(html, target)
    store.log_event("exported", record, format="pdf", path=str(target))
    return target
