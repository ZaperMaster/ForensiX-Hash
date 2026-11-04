"""Informe PDF: el HTML del informe impreso a PDF con Microsoft Edge (o Chrome) sin ventana.

Edge viene con Windows 10 y 11, así que el PDF se genera igual desde la app, la
web o la línea de comandos, sin dependencias extra.

El PDF lleva adjunto el registro firmado (JSON): así el mismo comprobante sirve
para importarlo en otro equipo y verificar allí la evidencia.
"""

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from time import monotonic, sleep

from pypdf import PdfReader, PdfWriter
from pypdf.errors import PyPdfError

from . import APP_NAME, devices, paths, report, store
from .record import seal_ok
from .signing import signature_status

TIMEOUT = 120
PDF_WAIT = 45
ATTACHMENT = "forensix-registro.json"
REQUIRED = ("id", "kind", "target", "algorithms", "hashes", "case", "created")


class ReportRejected(ValueError):
    """El informe se ha modificado: su sello o su firma no coinciden."""
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
    with tempfile.TemporaryDirectory(prefix="forensix-pdf-", ignore_cleanup_errors=True) as work:
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
        if not _wait_for_pdf(temporary):
            raise RuntimeError("No se pudo crear el PDF del informe.")
        shutil.copyfile(temporary, target)
    return target


def _wait_for_pdf(path: Path, timeout: float = PDF_WAIT) -> bool:
    """Espera a que el PDF esté completo.

    msedge.exe puede delegar en otro proceso y terminar antes de que el archivo
    exista, así que el fin del proceso no garantiza que el PDF esté escrito.
    """

    deadline = monotonic() + timeout
    while monotonic() < deadline:
        try:
            with open(path, "rb") as handle:
                handle.seek(-32, os.SEEK_END)
                if b"%%EOF" in handle.read():
                    return True
        except OSError:
            pass  # Aún no existe, o es demasiado corto
        sleep(0.1)
    return False


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
    attach_record(target, record)
    store.log_event("exported", record, format="pdf", path=str(target))
    return target


def attach_record(path: Path, record: dict) -> None:
    """Adjunta el registro firmado al PDF."""

    try:
        writer = PdfWriter(clone_from=str(path))
        writer.add_attachment(ATTACHMENT, report.to_json(record).encode("utf-8"))
        writer.add_metadata({"/Title": f"{APP_NAME} · {record['label']}", "/Creator": APP_NAME})
        writer.write(str(path))
    except PyPdfError as error:
        raise RuntimeError("No se pudo adjuntar el registro al PDF.") from error


def read_report(data: bytes) -> dict:
    """El registro de un informe PDF (o de su JSON). Comprueba el formato, el sello y la firma."""

    try:
        if data.startswith(b"%PDF"):
            data = PdfReader(io.BytesIO(data)).attachments[ATTACHMENT][0]
        record = json.loads(data)
        if not isinstance(record, dict) or record.get("format") != "forensix-hash/1" \
                or any(key not in record for key in REQUIRED):
            raise ValueError
        store.summary({**record, "verifications": record.get("verifications") or []})
    except (PyPdfError, ValueError, KeyError, IndexError, TypeError, AttributeError, OSError):
        raise ValueError("No es un informe de ForensiX Hash.") from None
    if not seal_ok(record) or signature_status(record) == "invalid":
        raise ReportRejected("El informe ha sido modificado: su sello o su firma no coinciden. No se importa.")
    return record


def import_report(data: bytes) -> tuple[dict, bool]:
    """Guarda en este equipo el registro de un informe. Devuelve (registro, ya existía)."""

    record = read_report(data)
    try:
        return store.load_record(record["id"]), True
    except KeyError:
        store.write_record(record)  # Sin volver a firmar: conserva la firma de quien lo creó
        store.log_event("imported", record)
        return record, False
