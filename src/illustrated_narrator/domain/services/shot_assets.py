"""Resuelve qué asset final tiene una toma en disco: imagen (generada con IA
o foto real) o clip de video real (B-roll de Pexels Video).

Un video real, si existe, siempre gana sobre la imagen: es el material de
mejor calidad de producción disponible para esa toma. `images_dir` conserva
su formato de siempre (`<shot_id>.png`) porque otros pasos (limpieza de
marcos, generación IA) asumen esa extensión; los videos reales viven aparte
en `media/videos/` para no mezclar formatos en ese directorio.
"""

from dataclasses import dataclass
from pathlib import Path

from illustrated_narrator.domain.services.retention_plan import Shot

_VIDEO_EXTENSIONS = {".mp4", ".mov", ".webm", ".mkv"}


@dataclass(frozen=True)
class ShotAsset:
    path: Path
    media_type: str  # "image" | "video"


def is_video_file(path: Path) -> bool:
    return path.suffix.lower() in _VIDEO_EXTENSIONS


def shot_image_path(images_dir: Path, shot: Shot) -> Path:
    return images_dir / f"{shot.shot_id}.png"


def shot_video_path(media_dir: Path, shot: Shot) -> Path:
    return media_dir / "videos" / f"{shot.shot_id}.mp4"


def resolve_shot_asset(images_dir: Path, media_dir: Path, shot: Shot) -> ShotAsset | None:
    """Video real primero si existe, si no imagen, si no None (toma sin
    resolver todavía — le toca generación IA)."""
    video = shot_video_path(media_dir, shot)
    if video.exists():
        return ShotAsset(video, "video")
    image = shot_image_path(images_dir, shot)
    if image.exists():
        return ShotAsset(image, "image")
    return None
