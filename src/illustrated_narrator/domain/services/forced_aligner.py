"""Alinea los planos[] del guion contra los timestamps reales de un audio ya
transcrito con palabras.

No hay que adivinar que se dijo -- el guion ya lo sabe. Solo hay que
encontrar cuando lo dijo. Se normalizan las palabras esperadas (concatenacion
de planos[].narracion) y las transcritas, se emparejan por similitud de
secuencia (difflib), y a cada plano se le asignan los timestamps reales de su
primera y ultima palabra emparejada.
"""

import difflib
import re
from dataclasses import dataclass, field

from illustrated_narrator.domain.entities.guion import Guion
from illustrated_narrator.domain.entities.transcript import Transcript, TranscriptWord

_PUNCT_RE = re.compile(r"[^\wáéíóúñü]", re.UNICODE)


def _normalize(word: str) -> str:
    return _PUNCT_RE.sub("", word.lower())


@dataclass(frozen=True)
class AlignmentResult:
    aligned_count: int
    total_planos: int
    unaligned_planos: list[str] = field(default_factory=list)


class AlignScriptToAudio:
    def __init__(self, min_match_ratio: float = 0.5) -> None:
        self._min_match_ratio = min_match_ratio

    def execute(self, guion: Guion, transcript: Transcript) -> AlignmentResult:
        expected_words: list[str] = []
        word_plano_index: list[int] = []
        for i, plano in enumerate(guion.planos):
            for w in plano.narracion.split():
                expected_words.append(_normalize(w))
                word_plano_index.append(i)

        transcribed_norm = [_normalize(w.text) for w in transcript.words]

        matcher = difflib.SequenceMatcher(a=expected_words, b=transcribed_norm, autojunk=False)
        matched_start: dict[int, float] = {}
        matched_end: dict[int, float] = {}
        for tag, i1, i2, j1, _j2 in matcher.get_opcodes():
            if tag != "equal":
                continue
            for offset in range(i2 - i1):
                expected_idx = i1 + offset
                real_word = transcript.words[j1 + offset]
                matched_start[expected_idx] = real_word.start_seconds
                matched_end[expected_idx] = real_word.end_seconds

        indices_by_plano: dict[int, list[int]] = {}
        for idx, plano_idx in enumerate(word_plano_index):
            indices_by_plano.setdefault(plano_idx, []).append(idx)

        unaligned: list[str] = []
        for i, plano in enumerate(guion.planos):
            indices = indices_by_plano.get(i, [])
            matched_indices = [idx for idx in indices if idx in matched_start]
            ratio = len(matched_indices) / len(indices) if indices else 0.0
            if ratio < self._min_match_ratio or not matched_indices:
                unaligned.append(plano.id)
                continue
            plano.inicio_real_seg = matched_start[matched_indices[0]]
            plano.fin_real_seg = matched_end[matched_indices[-1]]

        return AlignmentResult(
            aligned_count=len(guion.planos) - len(unaligned),
            total_planos=len(guion.planos),
            unaligned_planos=unaligned,
        )


def captioned_transcript(guion: Guion, transcript: Transcript) -> Transcript:
    """Devuelve un transcript con el TEXTO del guion (siempre correcto) pero
    los TIEMPOS reales de Whisper -- para quemar subtítulos.

    Sin esto, los subtítulos salen del reconocimiento crudo de Whisper, que
    puede errar nombres propios/técnicos (visto en un video real: "Chicxulub"
    transcrito como "Shisholup" y quemado así en pantalla). El guion ya sabe
    qué se dijo; solo hace falta CUÁNDO, que es lo único que Whisper aporta
    de forma confiable.
    """
    expected_words: list[str] = []
    for plano in guion.planos:
        expected_words.extend(plano.narracion.split())
    expected_norm = [_normalize(w) for w in expected_words]
    transcribed_norm = [_normalize(w.text) for w in transcript.words]

    matcher = difflib.SequenceMatcher(a=expected_norm, b=transcribed_norm, autojunk=False)
    opcodes = matcher.get_opcodes()

    def _next_known_start(op_idx: int) -> float | None:
        for tag, _i1, _i2, j1, j2 in opcodes[op_idx:]:
            if tag != "delete" and j2 > j1:
                return transcript.words[j1].start_seconds
        return None

    result: list[TranscriptWord] = []
    last_end = 0.0
    for op_idx, (tag, i1, i2, j1, j2) in enumerate(opcodes):
        script_slice = expected_words[i1:i2]
        n_script = i2 - i1
        n_trans = j2 - j1
        if tag == "insert" or n_script == 0:
            continue  # Whisper "escuchó" palabras que no están en el guion -- se descartan
        if tag == "equal" or (tag == "replace" and n_script == n_trans):
            for offset in range(n_script):
                w = transcript.words[j1 + offset]
                result.append(TranscriptWord(script_slice[offset], w.start_seconds, w.end_seconds))
                last_end = w.end_seconds
        elif n_trans > 0:
            # Cantidad distinta de palabras en guion vs. lo transcrito: se
            # reparte el tramo de tiempo real (inicio de la primera palabra
            # transcrita a fin de la última) en partes iguales entre las
            # palabras del guion -- aproximado, pero mejor que perderlas.
            span_start = transcript.words[j1].start_seconds
            span_end = transcript.words[j2 - 1].end_seconds
            step = max((span_end - span_start) / n_script, 0.01)
            for offset in range(n_script):
                s = span_start + offset * step
                e = span_start + (offset + 1) * step
                result.append(TranscriptWord(script_slice[offset], s, e))
            last_end = span_end
        else:
            # Whisper no reconoció NADA en este tramo (palabra completa
            # perdida/inaudible) -- se aprieta en el hueco entre lo último
            # conocido y lo próximo conocido, o justo después de lo último
            # si no hay nada más adelante.
            next_start = _next_known_start(op_idx + 1)
            span_start = last_end
            span_end = next_start if next_start is not None else last_end + 0.05 * n_script
            step = max((span_end - span_start) / n_script, 0.01)
            for offset in range(n_script):
                s = span_start + offset * step
                e = span_start + (offset + 1) * step
                result.append(TranscriptWord(script_slice[offset], s, e))
            last_end = span_end

    return Transcript(words=result, language=transcript.language)
