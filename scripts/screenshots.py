"""Capturas de docs/capturas/ para el README y la web, con la app web en marcha.

Usa Playwright con el Microsoft Edge instalado (no descarga navegadores):
    pip install playwright
    python -m web                      (en otra consola, como administrador para la lista de discos)
    python scripts/screenshots.py --record <id-disco> [--live-target D:\\archivo-grande.iso]
"""

import argparse
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "capturas"
SIZE = {"width": 1280, "height": 820}
CASE = {
    "examiner": "Alejandro Zapata",
    "organization": "ForensiX Lab",
    "case_number": "PRUEBA-001",
    "evidence_number": "EV-02",
    "description": "Carpeta Sonidos del pendrive USB SanDisk de 64 GB",
}


def settle(page) -> None:
    """Espera a que terminen las animaciones de entrada."""

    page.wait_for_timeout(450)


def fill_case(page) -> None:
    for name, value in CASE.items():
        page.fill(f"#caseForm [name={name}]", value)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8000")
    parser.add_argument("--record", required=True, help="registro para resultado.png e informe.png")
    parser.add_argument("--live-target", help="archivo grande para capturar el progreso")
    parser.add_argument("--output", default=str(Path.home() / "Documents" / "ForensiX Hash"))
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="msedge")
        context = browser.new_context(viewport=SIZE, device_scale_factor=1.25, color_scheme="light", locale="es-ES")
        context.add_init_script(f"localStorage.setItem('forensix.theme','light');"
                                f"localStorage.setItem('forensix.lang','es');"
                                f"localStorage.setItem('forensix.output',{args.output!r});")
        page = context.new_page()

        # 1 · Evidencia (carpeta)
        page.goto(f"{args.base}/#kind=directory")
        page.wait_for_selector("#algorithms .algorithm", state="attached")
        page.fill("#targetPath", r"D:\Sonidos")
        settle(page)
        page.screenshot(path=OUT / "nuevo.png")

        # 4 · Guardar, con el resumen
        page.click("#nextButton")
        fill_case(page)
        page.click("#nextButton")
        page.click("#nextButton")
        settle(page)
        page.screenshot(path=OUT / "guardar.png")

        # Discos
        page.goto(f"{args.base}/#kind=disk")
        page.wait_for_selector("input[name=disk]", timeout=30000)
        page.check("input[name=disk][value='\\\\\\\\.\\\\PhysicalDrive1']")
        settle(page)
        page.screenshot(path=OUT / "discos.png")

        if args.live_target:
            page.goto(f"{args.base}/")
            page.wait_for_selector("#algorithms .algorithm", state="attached")
            page.fill("#targetPath", args.live_target)
            page.click("#nextButton")
            fill_case(page)
            page.fill("#caseForm [name=evidence_number]", "EV-04")
            page.click("#nextButton")
            page.click("#nextButton")
            page.click("#startButton")
            page.wait_for_selector("#view-progress.active")
            time.sleep(6)
            page.screenshot(path=OUT / "progreso.png")
            page.click("#cancelButton")
            page.wait_for_selector("#view-new.active", timeout=30000)

        # Registro verificado con su informe PDF
        page.goto(f"{args.base}/#record={args.record}")
        page.wait_for_selector("#view-record.active .hash")
        settle(page)
        page.evaluate("document.querySelector('#toast').hidden = true")
        page.screenshot(path=OUT / "resultado.png")

        # Ajustes en tema oscuro
        dark = browser.new_context(viewport=SIZE, device_scale_factor=1.25, color_scheme="dark", locale="es-ES")
        dark.add_init_script("localStorage.setItem('forensix.theme','dark');localStorage.setItem('forensix.lang','es');")
        settings = dark.new_page()
        settings.goto(f"{args.base}/#view=settings")
        settings.wait_for_selector("#view-settings.active")
        settle(settings)
        settings.screenshot(path=OUT / "ajustes.png")

        report = context.new_page()
        report.set_viewport_size({"width": 1000, "height": 1300})
        report.goto(f"{args.base}/report/{args.record}")
        report.emulate_media(media="print")
        report.screenshot(path=OUT / "informe.png")
        browser.close()
    print(f"Capturas en {OUT}")


if __name__ == "__main__":
    main()
