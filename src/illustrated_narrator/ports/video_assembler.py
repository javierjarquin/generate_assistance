from abc import ABC, abstractmethod
from pathlib import Path

from illustrated_narrator.domain.services.shot_assets import ShotAsset


class VideoAssemblerPort(ABC):
    @abstractmethod
    def render_plano_clip(
        self,
        shots: list[ShotAsset],
        duration_seconds: float,
        pan_direction: str,
        dest: Path,
        overlay: str | None = None,
        motion=None,
    ) -> Path:
        """Renderiza el clip de un plano. Si `shots` trae varias tomas, se
        reparten la duración con cortes secos entre ellas (dinamismo). Cada
        toma puede ser una imagen (Ken Burns/parallax) o un clip de video
        real (B-roll de Pexels, sin zoompan — ya trae su propio movimiento).
        `motion` es un MotionProfile que fija la energía del movimiento."""

    @abstractmethod
    def render_end_card(self, text: str, duration_seconds: float, dest: Path) -> Path:
        """Tarjeta de cierre (CTA) sobre fondo oscuro."""

    @abstractmethod
    def render_intro_card(
        self,
        brand_name: str,
        duration_seconds: float,
        dest: Path,
        logo_path: Path | None = None,
    ) -> Path:
        """Tarjeta de apertura con el nombre de marca (mismo look que el CTA
        de cierre). `logo_path` está reservado para cuando haya un PNG de
        logo — hoy siempre None, solo texto vía ASS."""

    @abstractmethod
    def assemble(
        self,
        clip_paths: list[Path],
        ass_subtitle_path: Path | None,
        audio_path: Path,
        dest: Path,
        xfade_duration: float = 0.28,
        bed_path: Path | None = None,
        audio_delay_seconds: float = 0.0,
    ) -> Path: ...
