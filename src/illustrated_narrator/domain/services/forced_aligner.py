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
from illustrated_narrator.domain.entities.transcript import Transcript

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
