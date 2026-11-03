"""Genera el icono de la app (desktop/assets/app.ico) y las imágenes de la web (docs/).

Dibuja el mismo logo que web/static/brand/logo.svg (escudo con «#») a 1024 px y
lo reduce, para que se vea nítido en todos los tamaños.
Uso:  python desktop/make_icon.py
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
ICON = ROOT / "desktop" / "assets" / "app.ico"
DOCS = ROOT / "docs"
SIZES = [(16, 16), (20, 20), (24, 24), (32, 32), (40, 40), (48, 48), (64, 64), (128, 128), (256, 256)]

BG = (11, 18, 32, 255)
TEAL_LIGHT = (94, 234, 212)
TEAL = (14, 165, 183)
INK = (226, 232, 240, 255)


def _gradient(size: int) -> Image.Image:
    gradient = Image.new("RGBA", (size, size))
    pixels = gradient.load()
    for y in range(size):
        for x in range(size):
            k = (x + y) / (2 * size)
            pixels[x, y] = tuple(round(a + (b - a) * k) for a, b in zip(TEAL_LIGHT, TEAL)) + (255,)
    return gradient


def logo(size: int = 1024) -> Image.Image:
    """Logo en el sistema de coordenadas del SVG (64x64) escalado a `size`."""

    s = size / 64
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((0, 0, size - 1, size - 1), radius=14 * s, fill=BG)

    # Escudo: contorno con degradado
    points = [(32, 9), (50, 16), (50, 30)]
    for i in range(1, 21):  # curva derecha hasta la punta
        t = i / 20
        points.append((50 - 18 * t ** 1.6, 30 + 25 * t ** 0.9))
    for i in range(19, -1, -1):  # curva izquierda de vuelta
        t = i / 20
        points.append((14 + 18 * t ** 1.6, 30 + 25 * t ** 0.9))
    points += [(14, 30), (14, 16), (32, 9)]
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).line([(x * s, y * s) for x, y in points], fill=255, width=round(3.5 * s), joint="curve")
    image.paste(_gradient(size), (0, 0), mask)

    # Almohadilla «#»
    width = round(3.2 * s)
    for (x1, y1), (x2, y2) in (((27, 22), (24, 42)), ((38, 22), (35, 42)), ((21, 28), (43, 28)), ((20, 36), (42, 36))):
        draw.line((x1 * s, y1 * s, x2 * s, y2 * s), fill=INK, width=width)
        for x, y in ((x1, y1), (x2, y2)):
            r = width / 2
            draw.ellipse((x * s - r, y * s - r, x * s + r, y * s + r), fill=INK)
    return image


def social(path: Path) -> None:
    """Imagen para compartir el enlace (1280x640)."""

    image = Image.new("RGBA", (1280, 640), (10, 15, 26, 255))
    draw = ImageDraw.Draw(image)
    image.alpha_composite(logo(300).resize((300, 300), Image.LANCZOS), (110, 170))

    def font(size, bold=False):
        for name in (("segoeuib.ttf" if bold else "segoeui.ttf"), "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"):
            try:
                return ImageFont.truetype(name, size)
            except OSError:
                continue
        return ImageFont.load_default()

    draw.text((470, 200), "Forensi", font=font(96, True), fill=(230, 237, 246))
    x = 470 + draw.textlength("Forensi", font=font(96, True))
    draw.text((x, 200), "X", font=font(96, True), fill=(45, 212, 191))
    x += draw.textlength("X ", font=font(96, True))
    draw.text((x, 200), "Hash", font=font(96, True), fill=(230, 237, 246))
    draw.text((474, 330), "Hashes forenses verificados de archivos,", font=font(38), fill=(138, 154, 179))
    draw.text((474, 380), "carpetas y discos · cadena de custodia", font=font(38), fill=(138, 154, 179))
    draw.text((474, 455), "MD5 · SHA-1 · SHA-256 · SHA-512 · SHA3 · BLAKE2", font=font(28), fill=(45, 212, 191))
    image.convert("RGB").save(path, optimize=True)


def main() -> None:
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
