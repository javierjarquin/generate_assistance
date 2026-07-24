from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PublishResult:
    post_id: str
    url: str | None = None


class VideoPublisherPort(ABC):
    @abstractmethod
    def is_available(self) -> bool: ...

    @abstractmethod
    def publish(self, video_path: Path, title: str, description: str) -> PublishResult:
        """Sube `video_path` como Reel/video al destino configurado. Lanza
        RuntimeError con el mensaje de la API si falla -- publicar es una
        acción visible para terceros, no debe fallar en silencio."""
