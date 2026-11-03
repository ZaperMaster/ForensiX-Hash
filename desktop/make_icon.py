"""Genera el icono de la app (desktop/assets/app.ico) y las imágenes de la web (docs/).

Dibuja el mismo logo que web/static/brand/logo.svg (cuadrado azul con «#» blanco)
a 1024 px y lo reduce, para que se vea nítido en todos los tamaños.
Uso:  python desktop/make_icon.py
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
ICON = ROOT / "desktop" / "assets" / "app.ico"
DOCS = ROOT / "docs"
SIZES = [(16, 16), (20, 20), (24, 24), (32, 32), (40, 40), (48, 48), (64, 64), (128, 128), (256, 256)]

BLUE = (47, 107, 255)
CYAN = (24, 180, 245)
WHITE = (255, 255, 255, 255)
TEXT = (24, 24, 27)
MUTED = (113, 113, 122)


def _gradient(size: int) -> Image.Image:
    """Degradado diagonal azul → cian."""

    line = Image.new("RGBA", (2 * size, 1))
    for x in range(2 * size):
        k = x / (2 * size - 1)
        line.putpixel((x, 0), tuple(round(a + (b - a) * k) for a, b in zip(BLUE, CYAN)) + (255,))
    diagonal = line.resize((2 * size, 2 * size)).rotate(-45, resample=Image.BICUBIC)
    offset = size // 2
    return diagonal.crop((offset, offset, offset + size, offset + size))


def logo(size: int = 1024) -> Image.Image:
    """Logo en el sistema de coordenadas del SVG (64x64) escalado a `size`."""

    s = size / 64
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size - 1, size - 1), radius=16 * s, fill=255)
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    image.paste(_gradient(size), (0, 0), mask)

    draw = ImageDraw.Draw(image)
    width = round(5 * s)
    for x1, y1, x2, y2 in ((27, 18, 23, 46), (41, 18, 37, 46), (18, 27, 47, 27), (16, 37, 45, 37)):
        draw.line((x1 * s, y1 * s, x2 * s, y2 * s), fill=WHITE, width=width)
        for x, y in ((x1, y1), (x2, y2)):
            r = width / 2
            draw.ellipse((x * s - r, y * s - r, x * s + r, y * s + r), fill=WHITE)
    return image


def _font(size: int, bold: bool = False):
    for name in ("segoeuib.ttf" if bold else "segoeui.ttf", "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def social(path: Path) -> None:
    """Imagen para compartir el enlace (1280x640)."""

    image = Image.new("RGBA", (1280, 640), (246, 246, 248, 255))
    draw = ImageDraw.Draw(image)
    image.alpha_composite(logo(240).resize((240, 240), Image.LANCZOS), (120, 200))
    title = _font(96, bold=True)
    x = 420
    for text, color in (("Forensi", TEXT), ("X", BLUE), (" Hash", TEXT)):
        draw.text((x, 210), text, font=title, fill=color)
        x += draw.textlength(text, font=title)
    body = _font(36)
    draw.text((424, 345), "Hashes forenses verificados de archivos,", font=body, fill=(63, 63, 70))
    draw.text((424, 392), "carpetas y discos, con informe PDF", font=body, fill=(63, 63, 70))
    draw.text((424, 462), "MD5 · SHA-1 · SHA-256 · SHA-512 · SHA3 · BLAKE2", font=_font(26), fill=MUTED)
    image.convert("RGB").save(path, optimize=True)


def installer_images(folder: Path) -> None:
    """Imágenes del asistente de instalación (Inno Setup): lateral y pequeña, en varias escalas."""

    for scale in (100, 150, 200):
        width, height = (164 * scale // 100, 314 * scale // 100)
        side = Image.new("RGB", (width, height))
        side.paste(_gradient(max(width, height)).resize((width, height)).convert("RGB"))
        draw = ImageDraw.Draw(side)
        # «#» blanco grande, con las mismas proporciones que el logo (64x64)
        s, left, top = width * 0.9 / 64, width * 0.05, height * 0.18
        stroke = round(5 * s)
        for x1, y1, x2, y2 in ((27, 18, 23, 46), (41, 18, 37, 46), (18, 27, 47, 27), (16, 37, 45, 37)):
            points = [(left + x * s, top + y * s) for x, y in ((x1, y1), (x2, y2))]
            draw.line(points, fill=(255, 255, 255), width=stroke)
            for px, py in points:
                draw.ellipse((px - stroke / 2, py - stroke / 2, px + stroke / 2, py + stroke / 2), fill=(255, 255, 255))
        title = _font(18 * scale // 100, bold=True)
        draw.text((width // 2, height * 3 // 4), "ForensiX Hash", font=title, fill=(255, 255, 255), anchor="mm")
        side.save(folder / f"wizard-{scale}.bmp")

        size = 55 * scale // 100
        small = Image.new("RGB", (size, size), (255, 255, 255))
        small.paste(logo(512).resize((size, size), Image.LANCZOS), (0, 0), logo(512).resize((size, size), Image.LANCZOS))
        small.save(folder / f"wizard-small-{scale}.bmp")


def main() -> None:
    installer_images(ICON.parent)
    big = logo(1024)
    ICON.parent.mkdir(parents=True, exist_ok=True)
    big.resize((256, 256), Image.LANCZOS).save(ICON, format="ICO", sizes=SIZES)
    DOCS.mkdir(exist_ok=True)
    big.resize((256, 256), Image.LANCZOS).save(DOCS / "icon.png", optimize=True)
    big.resize((64, 64), Image.LANCZOS).save(DOCS / "favicon.png", optimize=True)
    social(DOCS / "social.png")
    print(f"Icono generado: {ICON}")


if __name__ == "__main__":
    main()
