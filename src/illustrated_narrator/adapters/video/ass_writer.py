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

# Palabras función: no deben quedar al FINAL de un chunk (dejan la frase colgando,
# ej. "pero lo" / "bajo el"). Si un chunk terminaría en una de estas, se arrastra
# a la palabra siguiente.
_FUNCTION_WORDS = frozenset(
    "el la los las un una unos unas de del al a y o u que qué se su sus mi tu "
    "lo le les me te nos con por para en pero sino ni como más muy es son fue "
    "entre sobre desde hasta hacia".split()
)


def _is_function_word(word: str) -> bool:
    return word.strip(".,;:!¡¿?").lower() in _FUNCTION_WORDS


def _wrap(text: str, max_chars: int = 20) -> str:
    """Parte una frase larga (gancho) en líneas equilibradas con \\N."""
    words = text.split()
    lines: list[str] = []
    current = ""
    for w in words:
        if current and len(current) + 1 + len(w) > max_chars:
            lines.append(current)
            current = w
        else:
            current = f"{current} {w}".strip()
    if current:
        lines.append(current)
    return "\\N".join(lines)

# Amarillo por defecto de la palabra hablada en el karaoke -- coincide con
# _DEFAULT_ACCENT_ASS de brand_palette.py (mismo valor, para que el default
# no cambie nada visualmente aunque ahora sea configurable).
_DEFAULT_ACCENT_ASS = "&H0000E8FF"

_HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,{font},{cap_size},{accent},&H00FFFFFF,&H00202020,&H00000000,-1,0,0,0,100,100,0,0,1,{cap_outline},{cap_shadow},2,80,80,{cap_margin},1
Style: Rotulo,{font},{rot_size},&H00FFFFFF,&H00FFFFFF,&H00202020,&H00000000,-1,0,0,0,100,100,0,0,1,3,1,8,60,60,70,1
Style: Titulo,{font},{title_size},&H00FFFFFF,&H00FFFFFF,&H00101010,&H00000000,-1,0,0,0,100,100,0,0,1,{title_outline},4,5,80,80,{title_margin},1
Style: Marca,{font},{marca_size},{accent},&H00FFFFFF,&H00101010,&H00000000,-1,0,0,0,100,100,2,0,1,{title_outline},3,2,80,80,{marca_margin},1

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
        # No cortar si el chunk terminaría en palabra función (queda colgando);
        # se permite un desborde leve para arrastrarla a la siguiente palabra.
        ends_bad = bool(current) and _is_function_word(current[-1].text)
        if current and (too_long or too_many) and not ends_bad:
            chunks.append(current)
            current, length = [], 0
            added = len(word.text)
        current.append(word)
        length += added
    if current:
        chunks.append(current)
    return chunks


def _chunk_dialogue(chunk: list[TranscriptWord], time_offset_seconds: float = 0.0) -> str:
    start = chunk[0].start_seconds + time_offset_seconds
    end = chunk[-1].end_seconds + 0.10 + time_offset_seconds
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
    accent_color_ass: str | None = None,
    time_offset_seconds: float = 0.0,
    brand_name: str | None = None,
    brand_duration: float = 2.0,
) -> Path:
    w, h = play_res
    vertical = h > w
    lines = [
        _HEADER.format(
            font=_FONT,
            w=w,
            h=h,
            accent=accent_color_ass or _DEFAULT_ACCENT_ASS,
            cap_size=int(h * 0.072) if not vertical else int(h * 0.046),
            cap_outline=max(3, int(h * 0.004)),
            cap_shadow=max(2, int(h * 0.0025)),
            cap_margin=int(h * 0.14),
            rot_size=int(h * 0.045) if not vertical else int(h * 0.030),
            title_size=int(h * 0.095) if not vertical else int(h * 0.055),
            title_outline=max(4, int(h * 0.005)),
            title_margin=int(h * 0.40),
            marca_size=int(h * 0.070) if not vertical else int(h * 0.045),
            marca_margin=int(h * 0.22),
        )
    ]

    # Nombre de marca en la tarjeta de intro (durante brand_duration): en la
    # banda inferior, debajo del logo, con pop de entrada.
    if brand_name:
        end = _format_ts(max(brand_duration - 0.1, 0.3))
        nombre = brand_name.upper().replace("\n", " ")
        lines.append(
            f"Dialogue: 1,0:00:00.20,{end},Marca,,0,0,0,,"
            f"{{\\fad(250,250)\\fscx70\\fscy70\\t(0,260,\\fscx100\\fscy100)}}{nombre}\n"
        )

    # Gancho: la frase de tensión (meta.gancho) si existe; si no, el título.
    # Los primeros 2.6s con POP de entrada (sin caja).
    gancho = (meta.gancho or meta.titulo) if meta else None
    if gancho:
        # Gancho largo (frase) se envuelve en varias líneas para no desbordar;
        # título corto queda en una línea.
        raw = gancho.upper().replace("\n", " ")
        texto = _wrap(raw, max_chars=18) if len(raw) > 20 else raw
        start = _format_ts(0.15 + time_offset_seconds)
        end = _format_ts(2.60 + time_offset_seconds)
        lines.append(
            f"Dialogue: 1,{start},{end},Titulo,,0,0,0,,"
            f"{{\\fad(200,300)\\fscx60\\fscy60\\t(0,220,\\fscx100\\fscy100)}}{texto}\n"
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
                lines.append(_chunk_dialogue(chunk, time_offset_seconds))
        if plano.texto_en_pantalla:
            start = _format_ts(plano.inicio_real_seg + time_offset_seconds)
            end = _format_ts(plano.fin_real_seg + time_offset_seconds)
            text = plano.texto_en_pantalla.replace("\n", "\\N")
            lines.append(
                f"Dialogue: 0,{start},{end},Rotulo,,0,0,0,,{{\\fad(200,200)}}{text}\n"
            )

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("".join(lines), encoding="utf-8")
    return dest
