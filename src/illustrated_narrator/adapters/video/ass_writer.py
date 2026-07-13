"""Genera subtítulos ASS con karaoke palabra-por-palabra + título de gancho.

Karaoke: cada palabra se ilumina en el momento exacto en que se dice (tags
\\kf con centisegundos reales de whisper). Las palabras de cada plano se
agrupan en líneas cortas (~26 caracteres) para lectura tipo Shorts/CapCut.

Si un plano trae texto_en_pantalla, se muestra además como rótulo superior
durante su ventana. El título del guion aparece como gancho en 0-2.8s.
"""

from pathlib import Path

from illustrated_narrator.domain.entities.guion import GuionMeta
from illustrated_narrator.domain.entities.plano import Plano
from illustrated_narrator.domain.entities.transcript import Transcript, TranscriptWord

_MAX_LINE_CHARS = 26

_HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Karaoke,Arial,{karaoke_size},&H0000E8FF,&H00FFFFFF,&H00101010,&H00000000,-1,0,0,0,100,100,1,0,1,4,1,2,60,60,{karaoke_margin},1
Style: Rotulo,Arial,{rotulo_size},&H00FFFFFF,&H00FFFFFF,&H00101010,&H00000000,-1,0,0,0,100,100,0,0,1,3,0,8,60,60,70,1
Style: Titulo,Arial,{title_size},&H00FFFFFF,&H00FFFFFF,&H00101010,&HB0000000,-1,0,0,0,100,100,1,0,3,18,0,5,80,80,60,1
Style: CTA,Arial,{title_size},&H0000E8FF,&H00FFFFFF,&H00101010,&H00000000,-1,0,0,0,100,100,1,0,1,5,1,5,80,80,60,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def _format_ts(seconds: float) -> str:
    seconds = max(0.0, seconds)
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def _words_for_plano(plano: Plano, transcript: Transcript) -> list[TranscriptWord]:
    if plano.inicio_real_seg is None or plano.fin_real_seg is None:
        return []
    lo = plano.inicio_real_seg - 0.05
    hi = plano.fin_real_seg + 0.05
    return [w for w in transcript.words if lo <= w.start_seconds and w.end_seconds <= hi]


def _group_lines(words: list[TranscriptWord]) -> list[list[TranscriptWord]]:
    lines: list[list[TranscriptWord]] = []
    current: list[TranscriptWord] = []
    length = 0
    for word in words:
        added = len(word.text) + (1 if current else 0)
        if current and length + added > _MAX_LINE_CHARS:
            lines.append(current)
            current, length = [], 0
            added = len(word.text)
        current.append(word)
        length += added
    if current:
        lines.append(current)
    return lines


def _karaoke_dialogue(line: list[TranscriptWord]) -> str:
    start = line[0].start_seconds
    end = line[-1].end_seconds + 0.12
    parts = []
    for i, word in enumerate(line):
        # \kf usa centisegundos; la duración de cada palabra absorbe el hueco
        # hasta la siguiente para que el barrido sea continuo
        word_end = line[i + 1].start_seconds if i + 1 < len(line) else word.end_seconds
        cs = max(1, round((word_end - word.start_seconds) * 100))
        parts.append(f"{{\\kf{cs}}}{word.text}")
    text = " ".join(parts)
    return f"Dialogue: 0,{_format_ts(start)},{_format_ts(end)},Karaoke,,0,0,0,,{text}\n"


def write_ass(
    planos: list[Plano],
    dest: Path,
    transcript: Transcript | None = None,
    meta: GuionMeta | None = None,
    play_res: tuple[int, int] = (1920, 1080),
    cta_text: str | None = None,
    cta_start_seconds: float | None = None,
    cta_duration: float = 3.0,
) -> Path:
    w, h = play_res
    vertical = h > w
    lines = [
        _HEADER.format(
            w=w,
            h=h,
            karaoke_size=int(h * 0.065) if not vertical else int(h * 0.042),
            karaoke_margin=int(h * 0.10),
            rotulo_size=int(h * 0.045) if not vertical else int(h * 0.030),
            title_size=int(h * 0.10) if not vertical else int(h * 0.055),
        )
    ]

    # Gancho: título grande con caja de contraste los primeros segundos
    if meta and meta.titulo:
        titulo = meta.titulo.upper().replace("\n", " ")
        lines.append(
            f"Dialogue: 1,0:00:00.20,0:00:02.80,Titulo,,0,0,0,,"
            f"{{\\fad(250,350)}} {titulo} \n"
        )

    # CTA de cierre: la tarjeta final necesita un texto que empuje a la acción
    if cta_text and cta_start_seconds is not None:
        start = _format_ts(cta_start_seconds + 0.2)
        end = _format_ts(cta_start_seconds + cta_duration)
        cta = cta_text.upper().replace("\n", "\\N")
        lines.append(
            f"Dialogue: 1,{start},{end},CTA,,0,0,0,,{{\\fad(300,300)}}{cta}\n"
        )

    for plano in planos:
        if plano.inicio_real_seg is None or plano.fin_real_seg is None:
            continue
        if transcript:
            for line in _group_lines(_words_for_plano(plano, transcript)):
                lines.append(_karaoke_dialogue(line))
        if plano.texto_en_pantalla:
            start = _format_ts(plano.inicio_real_seg)
            end = _format_ts(plano.fin_real_seg)
            text = plano.texto_en_pantalla.replace("\n", "\\N")
            lines.append(
                f"Dialogue: 0,{start},{end},Rotulo,,0,0,0,,{{\\fad(200,200)}}{text}\n"
            )

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("".join(lines), encoding="utf-8")
    return dest
