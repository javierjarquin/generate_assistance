"""Genera un archivo .ass (subtitulos ASS/libass) con el texto_en_pantalla de
cada plano. Una linea Dialogue por plano (no por palabra): a esta escala
(30-80 planos) es lo que mantiene el archivo inspeccionable a mano.

Nota: el resaltado palabra-por-palabra (karaoke, tags \\kf) requiere
timestamps reales por palabra dentro del plano -- se puede agregar cuando el
texto_en_pantalla se quiera sincronizar mas fino que "aparece durante todo el
plano". Por ahora cada plano simplemente muestra su texto_en_pantalla (si
tiene) durante su ventana real completa.
"""

from pathlib import Path

from illustrated_narrator.domain.entities.plano import Plano

_HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,Arial,54,&H00FFFFFF,&H0000D7FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,3,2,2,80,80,80,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def _format_ts(seconds: float) -> str:
    seconds = max(0.0, seconds)
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def write_ass(planos: list[Plano], dest: Path) -> Path:
    lines = [_HEADER]
    for plano in planos:
        if not plano.texto_en_pantalla:
            continue
        if plano.inicio_real_seg is None or plano.fin_real_seg is None:
            continue
        start = _format_ts(plano.inicio_real_seg)
        end = _format_ts(plano.fin_real_seg)
        text = plano.texto_en_pantalla.replace("\n", "\\N")
        lines.append(f"Dialogue: 0,{start},{end},Caption,,0,0,0,,{text}\n")

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("".join(lines), encoding="utf-8")
    return dest
