"""Tests del motor parallax 2.5D con imagen y profundidad sintéticas."""

import subprocess
from pathlib import Path

import pytest

np = pytest.importorskip("numpy")
cv2 = pytest.importorskip("cv2")

from illustrated_narrator.adapters.depth.onnx_depth import RadialDepthEstimator
from illustrated_narrator.adapters.video.parallax import render_parallax_clip
from illustrated_narrator.infrastructure.ffmpeg_locator import resolve_ffmpeg

FF = resolve_ffmpeg("ffmpeg")


def _synthetic_image(tmp_path: Path) -> Path:
    # gradiente + un cuadro central "cercano"
    img = np.zeros((240, 320, 3), np.uint8)
    img[:, :, 0] = np.linspace(0, 255, 320, dtype=np.uint8)[None, :]
    img[80:160, 120:200] = (40, 200, 240)
    p = tmp_path / "img.png"
    cv2.imwrite(str(p), img)
    return p


def _synthetic_depth() -> "np.ndarray":
    d = np.zeros((240, 320), np.float32)
    d[80:160, 120:200] = 1.0  # cuadro central cerca
    return cv2.GaussianBlur(d, (0, 0), 4)


def _probe_dims(path: Path) -> tuple[int, int, float]:
    ffprobe = str(Path(FF).parent / "ffprobe.exe")
    out = subprocess.run(
        [ffprobe, "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=width,height:format=duration", "-of", "default=noprint_wrappers=1:nokey=1",
         str(path)], capture_output=True, text=True,
    ).stdout.split()
    return int(out[0]), int(out[1]), float(out[2])


def test_parallax_renders_clip_with_motion(tmp_path: Path) -> None:
    img = _synthetic_image(tmp_path)
    depth = _synthetic_depth()
    dest = tmp_path / "plx.mp4"

    render_parallax_clip(
        FF, ["-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p"],
        img, depth, duration_seconds=2.0, fps=24, canvas=(320, 240), dest=dest,
        motion_name="impact",
    )

    assert dest.exists() and dest.stat().st_size > 0
    w, h, dur = _probe_dims(dest)
    assert (w, h) == (320, 240)
    assert 1.8 <= dur <= 2.2

    # hay movimiento entre dos frames separados (parallax activo)
    def frame(t, name):
        p = tmp_path / name
        subprocess.run([FF, "-hide_banner", "-loglevel", "error", "-ss", str(t),
                        "-i", str(dest), "-frames:v", "1", "-y", str(p)], check=True)
        return cv2.imread(str(p), cv2.IMREAD_GRAYSCALE).astype(np.int16)
    diff = np.abs(frame(0.2, "a.png") - frame(1.6, "b.png")).mean()
    assert diff > 1.0  # se mueve


def test_radial_depth_available_and_shaped(tmp_path: Path) -> None:
    img = _synthetic_image(tmp_path)
    est = RadialDepthEstimator()
    assert est.is_available()
    d = est.estimate(img)
    assert d.shape == (240, 320)
    assert 0.0 <= float(d.min()) and float(d.max()) <= 1.0
    # el centro está más cerca que las esquinas
    assert d[120, 160] > d[0, 0]
