"""Subtítulos ASS estilo Shorts/CapCut moderno (no "PowerPoint").

Estándar de retención aplicado (ver retention_standards.py):
- Chunks de 2-3 palabras (no líneas largas): lectura sin esfuerzo con sonido off.
- Cada chunk entra con un POP de escala (\\fscx/\\fscy + \\t) — el texto "salta",
  no aparece plano como una diapositiva.
- Palabra hablada resaltada en amarillo (\\kf con timestamps reales de whisper).
- Fuente gruesa (Arial Black) con borde grueso + sombra, SIN caja de fondo.
- Título de gancho y CTA con el mismo lenguaje (pop, sin caja).
"""

from pathlib import Path

from illustrated_narrator.domain.entities.guion import GuionMeta
from illustrated_narrator.domain.entities.plano import Plano
from illustrated_narrator.domain.entities.transcript import Transcript, TranscriptWord

# Chunks cortos: la investigación de retención pide 2-3 palabras por golpe
_MAX_CHUNK_WORDS = 3
_MAX_CHUNK_CHARS = 20

_FONT = "Arial Black"

_HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,{font},{cap_size},&H00FFFFFF,&H0000E8FF,&H00202020,&H00000000,-1,0,0,0,100,100,0,0,1,{cap_outline},{cap_shadow},2,80,80,{cap_margin},1
Style: Rotulo,{font},{rot_size},&H00FFFFFF,&H00FFFFFF,&H00202020,&H00000000,-1,0,0,0,100,100,0,0,1,3,1,8,60,60,70,1
Style: Titulo,{font},{title_size},&H0000E8FF,&H00FFFFFF,&H00101010,&H00000000,-1,0,0,0,100,100,0,0,1,{title_outline},4,5,80,80,{title_margin},1

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


def _chunk_words(words: list[TranscriptWord]) -> list[list[TranscriptWord]]:
    chunks: list[list[TranscriptWord]] = []
    current: list[TranscriptWord] = []
    length = 0
    for word in words:
        added = len(word.text) + (1 if current else 0)
        too_long = length + added > _MAX_CHUNK_CHARS
        too_many = len(current) >= _MAX_CHUNK_WORDS
        if current and (too_long or too_many):
            chunks.append(current)
            current, length = [], 0
            added = len(word.text)
        current.append(word)
        length += added
    if current:
        chunks.append(current)
    return chunks


def _chunk_dialogue(chunk: list[TranscriptWord]) -> str:
    start = chunk[0].start_seconds
    end = chunk[-1].end_seconds + 0.10
    # Pop de entrada: arranca al 72% y salta al 100% en 130ms
    pop = "{\\fad(40,30)\\fscx72\\fscy72\\t(0,130,\\fscx100\\fscy100)}"
    parts = []
    for i, word in enumerate(chunk):
        word_end = chunk[i + 1].start_seconds if i + 1 < len(chunk) else word.end_seconds
        cs = max(1, round((word_end - word.start_seconds) * 100))
        parts.append(f"{{\\kf{cs}}}{word.text}")
    text = pop + " ".join(parts)
    return f"Dialogue: 0,{_format_ts(start)},{_format_ts(end)},Caption,,0,0,0,,{text}\n"


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
            font=_FONT,
            w=w,
            h=h,
            cap_size=int(h * 0.072) if not vertical else int(h * 0.046),
            cap_outline=max(3, int(h * 0.004)),
            cap_shadow=max(2, int(h * 0.0025)),
            cap_margin=int(h * 0.14),
            rot_size=int(h * 0.045) if not vertical else int(h * 0.030),
            title_size=int(h * 0.095) if not vertical else int(h * 0.055),
            title_outline=max(4, int(h * 0.005)),
            title_margin=int(h * 0.40),
        )
    ]

    # Gancho: título grande con POP de entrada (sin caja). Los primeros 2.6s.
    if meta and meta.titulo:
        titulo = meta.titulo.upper().replace("\n", " ")
        lines.append(
            f"Dialogue: 1,0:00:00.15,0:00:02.60,Titulo,,0,0,0,,"
            f"{{\\fad(200,300)\\fscx60\\fscy60\\t(0,220,\\fscx100\\fscy100)}}{titulo}\n"
        )

    # CTA de cierre con el mismo lenguaje (pop, sin caja)
    if cta_text and cta_start_seconds is not None:
        start = _format_ts(cta_start_seconds + 0.2)
        end = _format_ts(cta_start_seconds + cta_duration)
        cta = cta_text.upper().replace("\n", "\\N")
        lines.append(
            f"Dialogue: 1,{start},{end},Titulo,,0,0,0,,"
            f"{{\\fad(250,300)\\fscx60\\fscy60\\t(0,220,\\fscx100\\fscy100)}}{cta}\n"
        )

    for plano in planos:
        if plano.inicio_real_seg is None or plano.fin_real_seg is None:
            continue
        if transcript:
            for chunk in _chunk_words(_words_for_plano(plano, transcript)):
                lines.append(_chunk_dialogue(chunk))
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
