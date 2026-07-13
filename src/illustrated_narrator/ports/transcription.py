from abc import ABC, abstractmethod
from pathlib import Path

from illustrated_narrator.domain.entities.transcript import Transcript


class TranscriptionPort(ABC):
    @abstractmethod
    def transcribe(self, audio_path: Path, language: str | None = None) -> Transcript: ...
