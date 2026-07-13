import pytest

from illustrated_narrator.domain.entities.guion import Guion, GuionMeta
from illustrated_narrator.domain.entities.plano import Plano, VisualSpec, VisualTipo
from illustrated_narrator.domain.entities.transcript import Transcript, TranscriptWord
from illustrated_narrator.domain.services.forced_aligner import AlignScriptToAudio


def _plano(id_: str, narracion: str) -> Plano:
    return Plano(
        id=id_, seccion="test", narracion=narracion,
        visual=VisualSpec(tipo=VisualTipo.IMAGEN_IA, prompt_ia="x"),
    )


def _words(text: str, start: float, per_word: float = 0.4) -> list[TranscriptWord]:
    words = []
    t = start
    for w in text.split():
        words.append(TranscriptWord(text=w, start_seconds=t, end_seconds=t + per_word))
        t += per_word
    return words


def test_aligns_planos_to_real_timestamps_in_order() -> None:
    guion = Guion(
        meta=GuionMeta(),
        planos=[
            _plano("p1", "hola mundo esto es una prueba"),
            _plano("p2", "el segundo plano continua aqui"),
        ],
    )
    # Simula narracion real leida sin pausas raras, empezando en 1.0s
    all_words = _words("hola mundo esto es una prueba el segundo plano continua aqui", start=1.0)
    transcript = Transcript(words=all_words, language="es")

    result = AlignScriptToAudio().execute(guion, transcript)

    assert result.aligned_count == 2
    assert result.unaligned_planos == []
    p1, p2 = guion.planos
    assert p1.inicio_real_seg == 1.0
    assert p1.fin_real_seg == pytest.approx(1.0 + 6 * 0.4)  # "prueba" end (6a palabra)
    # p2 empieza justo donde sigue "el" (7a palabra)
    assert p2.inicio_real_seg == pytest.approx(1.0 + 6 * 0.4)


def test_tolerates_minor_transcription_differences() -> None:
    guion = Guion(meta=GuionMeta(), planos=[_plano("p1", "Es una manana de primavera, hace 66 millones de anos.")])
    # Whisper transcribe sin puntuacion y con alguna diferencia menor de mayusculas
    transcript = Transcript(
        words=_words("es una manana de primavera hace 66 millones de años", start=0.0),
        language="es",
    )

    result = AlignScriptToAudio().execute(guion, transcript)

    assert result.aligned_count == 1
    plano = guion.planos[0]
    assert plano.inicio_real_seg == 0.0
    assert plano.duracion_real_seg is not None and plano.duracion_real_seg > 0


def test_flags_plano_as_unaligned_when_skipped_entirely() -> None:
    guion = Guion(
        meta=GuionMeta(),
        planos=[
            _plano("p1", "primera linea del guion"),
            _plano("p2", "segunda linea completamente distinta y ausente"),
            _plano("p3", "tercera linea del guion"),
        ],
    )
    # El usuario se salto p2 al grabar: el audio solo tiene p1 y p3
    transcript = Transcript(
        words=_words("primera linea del guion tercera linea del guion", start=0.0), language="es"
    )

    result = AlignScriptToAudio().execute(guion, transcript)

    assert "p2" in result.unaligned_planos
    assert guion.planos[1].inicio_real_seg is None
