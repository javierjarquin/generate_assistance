from pathlib import Path

from illustrated_narrator.domain.services.retention_plan import Shot
from illustrated_narrator.domain.services.shot_assets import (
    is_video_file,
    resolve_shot_asset,
    shot_image_path,
    shot_video_path,
)


def _shot(id_: str = "p1") -> Shot:
    return Shot(plano_id=id_, index=0, total=1)


def test_is_video_file() -> None:
    assert is_video_file(Path("clip.mp4")) is True
    assert is_video_file(Path("clip.MOV")) is True
    assert is_video_file(Path("photo.png")) is False


def test_resolve_returns_none_without_files(tmp_path: Path) -> None:
    assert resolve_shot_asset(tmp_path / "images", tmp_path / "media", _shot()) is None


def test_resolve_prefers_video_over_image(tmp_path: Path) -> None:
    images_dir = tmp_path / "images"
    media_dir = tmp_path / "media"
    shot = _shot()

    image_path = shot_image_path(images_dir, shot)
    image_path.parent.mkdir(parents=True, exist_ok=True)
    image_path.write_bytes(b"fake-png")

    video_path = shot_video_path(media_dir, shot)
    video_path.parent.mkdir(parents=True, exist_ok=True)
    video_path.write_bytes(b"fake-mp4")

    asset = resolve_shot_asset(images_dir, media_dir, shot)
    assert asset is not None
    assert asset.media_type == "video"
    assert asset.path == video_path


def test_resolve_falls_back_to_image(tmp_path: Path) -> None:
    images_dir = tmp_path / "images"
    media_dir = tmp_path / "media"
    shot = _shot()

    image_path = shot_image_path(images_dir, shot)
    image_path.parent.mkdir(parents=True, exist_ok=True)
    image_path.write_bytes(b"fake-png")

    asset = resolve_shot_asset(images_dir, media_dir, shot)
    assert asset is not None
    assert asset.media_type == "image"
    assert asset.path == image_path
