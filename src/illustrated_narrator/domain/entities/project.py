from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class NarrationProject:
    """Layout de carpetas de un proyecto de video: todo vive bajo root_dir."""

    slug: str
    root_dir: Path

    @property
    def script_path(self) -> Path:
        return self.root_dir / "guion.json"

    @property
    def audio_path(self) -> Path:
        return self.root_dir / "narracion.wav"

    @property
    def transcript_path(self) -> Path:
        return self.root_dir / "transcript.json"

    @property
    def planos_alineados_path(self) -> Path:
        return self.root_dir / "planos_alineados.json"

    @property
    def images_dir(self) -> Path:
        return self.root_dir / "images"

    @property
    def clips_dir(self) -> Path:
        return self.root_dir / "clips"

    @property
    def assets_dir(self) -> Path:
        return self.root_dir / "assets"

    @property
    def captions_path(self) -> Path:
        return self.root_dir / "captions.ass"

    @property
    def final_video_path(self) -> Path:
        return self.root_dir / "final.mp4"

    def ensure_dirs(self) -> None:
        self.root_dir.mkdir(parents=True, exist_ok=True)
        self.images_dir.mkdir(parents=True, exist_ok=True)
        self.clips_dir.mkdir(parents=True, exist_ok=True)
        self.assets_dir.mkdir(parents=True, exist_ok=True)
