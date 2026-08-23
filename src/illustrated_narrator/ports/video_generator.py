from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class VideoGenerationRequest:
    prompt: str
    negative_prompt: str = ""
    width: int = 512
    height: int = 512
    duration_seconds: float = 4.0
    fps: int = 8


class VideoGeneratorPort(ABC):
    @abstractmethod
    def is_available(self) -> bool: ...

    @abstractmethod
    def generate(self, request: VideoGenerationRequest, dest: Path) -> Path:
        """Genera un clip de video y lo escribe en `dest` (mp4). Lanza si
        falla -- el llamador decide qué hacer (último recurso, no hay más
        fallback después de esto)."""