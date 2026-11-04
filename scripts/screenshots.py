"""Capturas de docs/capturas/ para el README y la web, con la versión web en marcha.

Usa Playwright con el Microsoft Edge instalado (no descarga navegadores). Conviene
arrancar la web con una carpeta de datos de demostración, para no publicar registros reales:
    pip install playwright
    set FORENSIX_HASH_HOME=C:\\ruta\\demo  &&  python -m uvicorn web.server:app --port 8010
    python scripts/screenshots.py --base http://127.0.0.1:8010 --record <id> --mismatch <id> --live-target grande.bin
Al final compone docs/capturas/portada.png (tema claro y oscuro superpuestos).
"""

import argparse
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "capturas"
SIZE = {"width": 1360, "height": 860}
CASE = {
    "examiner": "Alejandro Zapata",
    "organization": "ForensiX Lab",
    "case_number": "2026-0417",
    "evidence_number": "EV-02",
    "description": "Carpeta Sonidos del pendrive USB SanDisk de 64 GB",
}


def new_page(browser, theme: str, output: str):
    context = browser.new_context(viewport=SIZE, device_scale_factor=1.5, color_scheme=theme, locale="es-ES")
    context.add_init_script(f"localStorage.setItem('forensix.theme',{theme!r});"
                            "localStorage.setItem('forensix.lang','es');"
                            f"localStorage.setItem('forensix.output',{output!r});"
                            "localStorage.setItem('forensix.autoUpdate','0');")
    return context.new_page()


def shot(page, name: str) -> None:
    page.mouse.move(0, SIZE["height"] - 1)  # Sin resaltes por el ratón encima
    page.wait_for_timeout(500)  # Animaciones de entrada
    page.evaluate("document.querySelector('#toast').hidden = true")
    page.screenshot(path=OUT / f"{name}.png")


def wizard(page, base: str, target: str, prefix: str, steps=(1, 2, 3, 4)) -> None:
    page.goto(f"{base}/#kind=directory")
    page.wait_for_selector("#algorithms .algorithm", state="attached")
    page.fill("#targetPath", target)
    if 1 in steps:
        shot(page, f"{prefix}1-evidencia")
    page.click("#nextButton")
    for name, value in CASE.items():
        page.fill(f"#caseForm [name={name}]", value)
    if 2 in steps:
        shot(page, f"{prefix}2-datos")
    page.click("#nextButton")
    page.check("#algorithms input[value=sha512]")
    if 3 in steps:
        shot(page, f"{prefix}3-hash")
    page.click("#nextButton")
    if 4 in steps:
        shot(page, f"{prefix}4-guardar")


def cover(light: Path, dark: Path, target: Path) -> None:
    """Portada: captura clara delante y oscura detrás, con sombra suave."""

    width = 2400
    canvas = Image.new("RGBA", (width, 1500), (0, 0, 0, 0))
    scale = 0.78
    front = Image.open(light).convert("RGBA")
    back = Image.open(dark).convert("RGBA")
    size = (int(width * scale), int(width * scale * front.height / front.width))
    front, back = front.resize(size, Image.LANCZOS), back.resize(size, Image.LANCZOS)

    def rounded(image):
        mask = Image.new("L", image.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, *image.size), radius=28, fill=255)
        image.putalpha(mask)
        return image

    def shadow(position, image):
        layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        box = Image.new("RGBA", image.size, (12, 16, 30, 110))
        layer.paste(box, (position[0], position[1] + 30), rounded(box.copy()))
        canvas.alpha_composite(layer.filter(ImageFilter.GaussianBlur(40)))

    positions = ((width - size[0] - 40, 40), (40, 1500 - size[1] - 60))
    for position, image in zip(positions, (rounded(back), rounded(front))):
        shadow(position, image)
        canvas.alpha_composite(image, position)
    canvas.save(target, optimize=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8010")
    parser.add_argument("--record", required=True, help="registro verificado (resultado y PDF)")
    parser.add_argument("--mismatch", help="registro que NO COINCIDE")
    parser.add_argument("--live-target", help="archivo grande para capturar el progreso")
    parser.add_argument("--output", default=r"C:\Users\Alejandro\Documents\ForensiX Hash")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="msedge")
        light = new_page(browser, "light", args.output)
        dark = new_page(browser, "dark", args.output)

        wizard(light, args.base, r"D:\Sonidos", "paso")

        if args.live_target:
            light.goto(f"{args.base}/")
            light.wait_for_selector("#algorithms .algorithm", state="attached")
            light.click(".kind[data-kind=file]")
            light.fill("#targetPath", args.live_target)
            light.click("#nextButton")
            for name, value in CASE.items():
                light.fill(f"#caseForm [name={name}]", value)
            light.fill("#caseForm [name=evidence_number]", "EV-09")
            light.click("#nextButton")
            light.click("#nextButton")
            light.click("#startButton")
            light.wait_for_selector("#view-progress.active")
            time.sleep(1.2)
            light.evaluate("document.querySelector('#statCurrent').textContent = 'imagen-pendrive.dd'")
            shot(light, "progreso")
            light.click("#cancelButton")
            light.wait_for_selector("#view-new.active", timeout=30000)

        for page, prefix in ((light, ""), (dark, "oscuro-")):
            page.goto(f"{args.base}/#record={args.record}")
            page.wait_for_selector("#view-record.active .hash")
            shot(page, f"{prefix}resultado")
        if args.mismatch:
            light.goto(f"{args.base}/#record={args.mismatch}")
            light.wait_for_selector("#view-record.active .hash")
            shot(light, "no-coincide")

        light.goto(f"{args.base}/#view=history")
        light.wait_for_selector(".history-item")
        shot(light, "registros")
        light.goto(f"{args.base}/#view=custody")
        light.wait_for_selector("#custodyBody tr")
        shot(light, "custodia")
        dark.goto(f"{args.base}/#view=settings")
        dark.wait_for_selector("#view-settings.active")
        shot(dark, "ajustes")

        report = browser.new_page(viewport={"width": 1000, "height": 1300}, device_scale_factor=1.5)
        report.goto(f"{args.base}/report/{args.record}")
        report.emulate_media(media="print")
        # Sin el nombre real del equipo ni del usuario en una imagen pública
        report.evaluate("""() => document.querySelectorAll('td').forEach(cell => {
            const label = cell.previousElementSibling?.textContent;
            if (['Equipo', 'Usuario del sistema'].includes(label)) cell.textContent = 'LAB-01';
        })""")
        report.screenshot(path=OUT / "informe.png")
        browser.close()

    cover(OUT / "resultado.png", OUT / "oscuro-resultado.png", OUT / "portada.png")
    print(f"Capturas en {OUT}")


if __name__ == "__main__":
    main()
