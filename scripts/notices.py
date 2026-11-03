"""Genera THIRD_PARTY_NOTICES.md con las librerías que se incluyen en el .exe y sus licencias.

Recorre las dependencias de desktop/requirements.txt (sin las herramientas de
desarrollo) a partir de los paquetes instalados y copia el texto de cada licencia.
Uso:  python scripts/notices.py
"""

import re
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "THIRD_PARTY_NOTICES.md"
# Lo que va dentro del .exe. pytest, httpx2 y pillow solo se usan para probar o generar iconos;
# PyInstaller aporta su cargador, que se declara aparte.
ROOTS = ["fastapi", "uvicorn", "pywebview", "cryptography"]
# Paquetes que no declaran la licencia en sus metadatos (comprobada en su repositorio).
KNOWN_LICENSES = {"clr_loader": "MIT"}
LICENSE_FILES = re.compile(r"(LICEN[CS]E|COPYING|NOTICE|AUTHORS)", re.IGNORECASE)


def _name(requirement: str) -> str:
    return re.split(r"[\s;<>=!~\[(]", requirement, maxsplit=1)[0].lower().replace("_", "-")


def dependencies() -> list[metadata.Distribution]:
    seen: dict[str, metadata.Distribution] = {}
    pending = list(ROOTS)
    while pending:
        name = pending.pop()
        if name in seen:
            continue
        try:
            dist = metadata.distribution(name)
        except metadata.PackageNotFoundError:
            continue
        seen[name] = dist
        for requirement in dist.requires or []:
            if "extra ==" in requirement:
                continue
            marker = requirement.split(";", 1)[1] if ";" in requirement else ""
            if "sys_platform" in marker and "win32" not in marker and "!=" not in marker:
                continue
            pending.append(_name(requirement))
    return sorted(seen.values(), key=lambda d: d.metadata["Name"].lower())


def license_name(dist: metadata.Distribution) -> str:
    meta = dist.metadata
    if meta.get("License-Expression"):
        return meta["License-Expression"]
    classifiers = [c.split("::")[-1].strip() for c in meta.get_all("Classifier") or [] if c.startswith("License ::")]
    if classifiers:
        return ", ".join(classifiers)
    text = (meta.get("License") or "").strip()
    return text.splitlines()[0] if text else KNOWN_LICENSES.get(meta["Name"].lower(), "Ver el texto de la licencia")


def license_texts(dist: metadata.Distribution) -> list[str]:
    texts = []
    for file in dist.files or []:
        if LICENSE_FILES.search(file.name) and file.suffix.lower() in ("", ".txt", ".md", ".rst"):
            try:
                texts.append(file.read_text(encoding="utf-8").strip())
            except (OSError, UnicodeDecodeError):
                continue
    return texts


def main() -> None:
    dists = dependencies()
    lines = [
        "# Avisos de terceros",
        "",
        "ForensiX Hash incluye en su ejecutable las siguientes librerías de código abierto. Cada una se",
        "distribuye bajo su propia licencia, que se reproduce a continuación. Generado con `python scripts/notices.py`.",
        "",
        "| Librería | Versión | Licencia |",
        "|---|---|---|",
    ]
    for dist in dists:
        lines.append(f"| {dist.metadata['Name']} | {dist.version} | {license_name(dist)} |")
    lines += ["| PyInstaller (cargador del .exe) | — | GPL-2.0 con excepción para el cargador |", ""]
    lines += [
        "El **cargador de PyInstaller** se distribuye bajo GPL-2.0 con una excepción que permite usarlo en",
        "programas con cualquier licencia: <https://github.com/pyinstaller/pyinstaller/blob/develop/COPYING.txt>.",
        "El intérprete de **Python** se distribuye bajo la PSF License: <https://docs.python.org/3/license.html>.",
        "",
    ]
    for dist in dists:
        lines += [f"## {dist.metadata['Name']} {dist.version}", ""]
        home = dist.metadata.get("Home-page") or next(
            (url.split(",", 1)[1].strip() for url in dist.metadata.get_all("Project-URL") or []), "")
        if home:
            lines += [f"<{home}>", ""]
        texts = license_texts(dist)
        if texts:
            for text in texts:
                lines += ["```text", text, "```", ""]
        else:
            lines += [f"Licencia: {license_name(dist)}", ""]
    OUTPUT.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print(f"{OUTPUT.name}: {len(dists)} librerías")


if __name__ == "__main__":
    main()
