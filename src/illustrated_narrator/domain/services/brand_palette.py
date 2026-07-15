"""Conversión de un color de marca (#RRGGBB) a los formatos que necesita cada
adaptador: ASS (subtítulos) usa BGR sin alfa, ffmpeg lavfi usa 0xRRGGBB.

El default (#FFE800) reproduce exactamente el amarillo hardcodeado que ya
tenía el karaoke (&H0000E8FF), así que con la configuración por defecto nada
cambia visualmente aunque el color ahora sea configurable.
"""

DEFAULT_ACCENT_HEX = "#FFE800"


def hex_to_ass_color(hex_color: str) -> str:
    """'#RRGGBB' -> '&H00BBGGRR' (formato ASS: BGR, sin canal alfa)."""
    h = hex_color.lstrip("#")
    r, g, b = h[0:2], h[2:4], h[4:6]
    return f"&H00{b}{g}{r}".upper()


def hex_to_ffmpeg_color(hex_color: str) -> str:
    """'#RRGGBB' -> '0xRRGGBB' (formato color lavfi de ffmpeg)."""
    return f"0x{hex_color.lstrip('#').upper()}"
