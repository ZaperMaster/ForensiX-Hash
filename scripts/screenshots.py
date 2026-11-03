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
    "evidence_number": "EV-01",
    "description": "Pendrive USB SanDisk 3.2Gen1 de 64 GB",
}


def fill_case(page) -> None:
    for name, value in CASE.items():
        page.fill(f"#caseForm [name={name}]", value)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8000")
    parser.add_argument("--record", required=True, help="registro para resultado.png e informe.png")
    parser.add_argument("--live-target", help="archivo grande para capturar el progreso")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="msedge")
        context = browser.new_context(viewport=SIZE, device_scale_factor=1.25, color_scheme="dark", locale="es-ES")
        page = context.new_page()

        page.goto(f"{args.base}/#kind=directory")
        page.wait_for_selector("#algorithms .chip")
        page.fill("#targetPath", r"D:\Sonidos")
        fill_case(page)
        page.evaluate("document.querySelector('#caseForm [name=evidence_number]').value = 'EV-02'")
        page.screenshot(path=OUT / "nuevo.png")

        page.goto(f"{args.base}/#kind=disk")
        page.wait_for_selector("input[name=disk]", timeout=30000)
        page.check("input[name=disk][value='\\\\\\\\.\\\\PhysicalDrive1']")
        page.evaluate("document.querySelector('#diskPicker').scrollIntoView()")
        page.screenshot(path=OUT / "discos.png")

        if args.live_target:
            page.goto(f"{args.base}/")
            page.wait_for_selector("#algorithms .chip")
            page.fill("#targetPath", args.live_target)
            fill_case(page)
            page.click("#startButton")
            page.wait_for_selector("#view-progress.active")
            time.sleep(6)
            page.screenshot(path=OUT / "progreso.png")
            page.click("#cancelButton")
            page.wait_for_selector("#view-new.active", timeout=30000)

        page.goto(f"{args.base}/#record={args.record}")
        page.wait_for_selector("#view-record.active .hash")
        page.screenshot(path=OUT / "resultado.png")

        report = context.new_page()
        report.set_viewport_size({"width": 1000, "height": 1300})
        report.goto(f"{args.base}/report/{args.record}")
        report.emulate_media(media="print")
        report.screenshot(path=OUT / "informe.png")
        browser.close()
    print(f"Capturas en {OUT}")


if __name__ == "__main__":
    main()
