from abc import ABC, abstractmethod
from pathlib import Path


class VideoAssemblerPort(ABC):
    @abstractmethod
    def render_plano_clip(
        self,
        image_paths: list[Path],
        duration_seconds: float,
        pan_direction: str,
        dest: Path,
        overlay: str | None = None,
        shake: bool = False,
    ) -> Path:
        """Renderiza el clip de un plano. Si image_paths trae varias imágenes,
        se reparten la duración con cortes secos entre ellas (dinamismo)."""

    @abstractmethod
    def render_end_card(self, text: str, duration_seconds: float, dest: Path) -> Path:
        """Tarjeta de cierre (CTA) sobre fondo oscuro."""

    @abstractmethod
    def assemble(
        self,
        clip_paths: list[Path],
        ass_subtitle_path: Path | None,
        audio_path: Path,
        dest: Path,
        xfade_duration: float = 0.28,
        bed_path: Path | None = None,
    ) -> Path: ...
