"""Generador de imágenes placeholder: carteles locales con PIL, sin A1111.

Sirve para probar el pipeline completo (transcripción, alineación, Ken Burns,
subtítulos, ensamblado) sin Stable Diffusion instalado. Cada plano recibe un
cartel con fondo de color determinista (derivado del seed) y su prompt como
texto, para distinguir visualmente los planos en el video de prueba.
"""

import colorsys
import textwrap
from pathlib import Path

from illustrated_narrator.ports.image_generator import ImageGenerationRequest, ImageGeneratorPort

_W, _H = 1280, 720


def _font(size: int):
    from PIL import ImageFont

    for name in ("segoeui.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


class PlaceholderImageAdapter(ImageGeneratorPort):
    def is_available(self) -> bool:
        return True

    def generate(self, request: ImageGenerationRequest, dest: Path) -> Path:
        from PIL import Image, ImageDraw

        # Tono determinista por seed: cada plano con color propio, reproducible
        hue = (request.seed % 360) / 360.0
        r, g, b = colorsys.hsv_to_rgb(hue, 0.45, 0.35)
        base = (int(r * 255), int(g * 255), int(b * 255))

        image = Image.new("RGB", (_W, _H), base)
        draw = ImageDraw.Draw(image)

        # Degradado vertical sencillo hacia oscuro para dar profundidad
        for y in range(_H):
            factor = 1.0 - 0.45 * (y / _H)
            draw.line(
                [(0, y), (_W, y)],
                fill=(int(base[0] * factor), int(base[1] * factor), int(base[2] * factor)),
            )

        label = request.label.strip() or request.prompt.split(",")[0].strip() or "plano"
        wrapped = textwrap.fill(label, width=34)
        draw.multiline_text(
            (_W // 2, _H // 2),
            wrapped,
            font=_font(56),
            fill=(240, 236, 228),
            anchor="mm",
            align="center",
        )
        draw.text(
            (_W // 2, _H - 60),
            "imagen de prueba — sin Stable Diffusion",
            font=_font(24),
            fill=(200, 196, 188),
            anchor="mm",
        )

        dest.parent.mkdir(parents=True, exist_ok=True)
        image.save(dest, "PNG")
        return dest
