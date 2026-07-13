"""Transcripción con faster-whisper (CPU, int8), con timestamps por palabra.

A diferencia del adaptador de shorts-factory (que solo usa timestamps por
frase), aquí SÍ se pide word_timestamps=True: la alineación forzada contra el
guion conocido (ver AlignScriptToAudio) necesita saber cuándo empieza/termina
cada palabra, no solo cada oración.
"""

import logging
from pathlib import Path

from illustrated_narrator.domain.entities.transcript import Transcript, TranscriptWord
from illustrated_narrator.ports.transcription import TranscriptionPort

logger = logging.getLogger(__name__)


class FasterWhisperTranscriber(TranscriptionPort):
    def __init__(
        self,
        model_size: str = "small",
        device: str = "cpu",
        compute_type: str = "int8",
        cpu_threads: int = 0,
    ) -> None:
        self._model_size = model_size
        self._device = device
        self._compute_type = compute_type
        self._cpu_threads = cpu_threads
        self._model = None

    def _load_model(self):
        if self._model is None:
            from faster_whisper import WhisperModel

            logger.info(
                "Cargando modelo whisper '%s' (%s, %s)",
                self._model_size,
                self._device,
                self._compute_type,
            )
            self._model = WhisperModel(
                self._model_size,
                device=self._device,
                compute_type=self._compute_type,
                cpu_threads=self._cpu_threads,
            )
        return self._model

    def transcribe(self, audio_path: Path, language: str | None = None) -> Transcript:
        model = self._load_model()
        segments, info = model.transcribe(
            str(audio_path), language=language, vad_filter=True, word_timestamps=True
        )
        logger.info(
            "Transcribiendo %s (~%.0fs de audio, %s)…",
            audio_path.name, info.duration, language or "detectando idioma",
        )
        words: list[TranscriptWord] = []
        last_logged = 0.0
        for segment in segments:
            for w in segment.words or []:
                words.append(
                    TranscriptWord(
                        text=w.word.strip(), start_seconds=float(w.start), end_seconds=float(w.end)
                    )
                )
            if segment.end - last_logged >= 30:
                logger.info("  %s: %.0fs / %.0fs transcritos", audio_path.name, segment.end, info.duration)
                last_logged = segment.end

        logger.info("Transcrito %s: %d palabras, idioma %s", audio_path.name, len(words), info.language)
        return Transcript(words=words, language=info.language)
