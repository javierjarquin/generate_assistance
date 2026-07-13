from abc import ABC, abstractmethod
from pathlib import Path


class VideoAssemblerPort(ABC):
    @abstractmethod
    def render_plano_clip(
        self,
        image_path: Path,
        duration_seconds: float,
        pan_direction: str,
        dest: Path,
        overlay: str | None = None,
        shake: bool = False,
    ) -> Path: ...

    @abstractmethod
    def assemble(
        self,
        clip_paths: list[Path],
        ass_subtitle_path: Path | None,
        audio_path: Path,
        dest: Path,
        xfade_duration: float = 0.5,
        bed_path: Path | None = None,
    ) -> Path: ...
