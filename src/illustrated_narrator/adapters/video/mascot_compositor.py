"""Compositor de mascota: superpone un personaje animado que "presenta" el video.

Toma la carpeta de la mascota (sprites por acción), un plan de acciones (del
mascot_director) y el audio de narración, y produce el video final con la
mascota compuesta en una esquina. La boca se mueve por presencia de voz
(lip-sync de amplitud): mientras hay voz usa la acción activa (p. ej. `talk`,
con boca en movimiento en el arte); en los silencios cae a `idle`.

CPU puro: sprites con PIL, envolvente con numpy, composición con ffmpeg.
"""

import logging
import subprocess
from pathlib import Path

from illustrated_narrator.domain.services.mascot_director import (
    ALL_ACTIONS,
    IDLE,
    REQUIRED_ACTIONS,
    TALK,
    MascotSegment,
    action_at,
)

logger = logging.getLogger(__name__)

_IMG_EXTS = (".png", ".webp")
_ANIM_EXTS = (".gif", ".apng", ".png", ".webp", ".webm", ".mov")
_POSITIONS = ("bottom-right", "bottom-left", "bottom-center")


class MascotAssetsError(Exception):
    pass


def available_actions(mascot_dir: Path) -> set[str]:
    """Acciones presentes en la carpeta (subcarpeta de PNGs o archivo animado)."""
    found: set[str] = set()
    for action in ALL_ACTIONS:
        if _resolve_action_source(mascot_dir, action) is not None:
            found.add(action)
    return found


def _resolve_action_source(mascot_dir: Path, action: str):
    sub = mascot_dir / action
    if sub.is_dir() and any(p.suffix.lower() in _IMG_EXTS for p in sub.iterdir()):
        return sub
    for ext in _ANIM_EXTS:
        f = mascot_dir / f"{action}{ext}"
        if f.exists():
            return f
    return None


def _load_frames(source: Path, target_h: int, ffmpeg: str):
    """Devuelve lista de frames RGBA (PIL) escalados a `target_h` de alto."""
    from PIL import Image, ImageSequence

    frames = []
    if source.is_dir():
        for p in sorted(source.iterdir()):
            if p.suffix.lower() in _IMG_EXTS:
                frames.append(Image.open(p).convert("RGBA"))
    elif source.suffix.lower() in (".webm", ".mov"):
        # extraer frames con alpha vía ffmpeg
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            subprocess.run(
                [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(source),
                 "-vf", "format=rgba", f"{td}/%04d.png"],
                check=True,
            )
            for p in sorted(Path(td).glob("*.png")):
                frames.append(Image.open(p).convert("RGBA"))
    else:  # gif / apng / webp animado (o imagen única)
        im = Image.open(source)
        for fr in ImageSequence.Iterator(im):
            frames.append(fr.convert("RGBA"))
    if not frames:
        raise MascotAssetsError(f"sin frames en {source}")
    # escalar a target_h manteniendo proporción
    out = []
    for fr in frames:
        if fr.height != target_h:
            w = max(1, round(fr.width * target_h / fr.height))
            fr = fr.resize((w, target_h))
        out.append(fr)
    return out


def _voice_envelope(audio_path: Path, ffmpeg: str, fps: int, n_frames: int, sr: int = 16000):
    """RMS normalizado (0..1) por frame de video, desde el wav de narración."""
    import numpy as np

    raw = subprocess.run(
        [ffmpeg, "-hide_banner", "-loglevel", "error", "-i", str(audio_path),
         "-ac", "1", "-ar", str(sr), "-f", "s16le", "-"],
        capture_output=True, check=True,
    ).stdout
    samples = np.frombuffer(raw, np.int16).astype(np.float32) / 32768.0
    per = max(1, sr // fps)
    env = np.zeros(n_frames, np.float32)
    for i in range(n_frames):
        seg = samples[i * per:(i + 1) * per]
        if len(seg):
            env[i] = float(np.sqrt((seg ** 2).mean()))
    peak = env.max()
    return env / peak if peak > 1e-6 else env


def composite_mascot(
    ffmpeg: str,
    encode_args: list[str],
    final_video: Path,
    audio_path: Path,
    mascot_dir: Path,
    segments: list[MascotSegment],
    dest: Path,
    fps: int = 30,
    canvas: tuple[int, int] = (1920, 1080),
    height_frac: float = 0.34,
    position: str = "bottom-right",
    mascot_fps: int = 12,
    voice_threshold: float = 0.06,
    intro_offset: float = 0.0,
) -> Path:
    """Compone la mascota animada sobre `final_video` y escribe `dest`."""
    import numpy as np
    from PIL import Image

    missing = [a for a in REQUIRED_ACTIONS if _resolve_action_source(mascot_dir, a) is None]
    if missing:
        raise MascotAssetsError(f"faltan acciones obligatorias: {', '.join(missing)}")
    if position not in _POSITIONS:
        position = "bottom-right"

    w, h = canvas
    target_h = int(h * height_frac)
    actions = {}
    for action in ALL_ACTIONS:
        src = _resolve_action_source(mascot_dir, action)
        if src is not None:
            actions[action] = _load_frames(src, target_h, ffmpeg)

    region_w = max(fr.width for frs in actions.values() for fr in frs)
    region_h = max(fr.height for frs in actions.values() for fr in frs)
    margin = int(h * 0.02)
    if position == "bottom-right":
        ox, oy = w - region_w - margin, h - region_h - margin
    elif position == "bottom-left":
        ox, oy = margin, h - region_h - margin
    else:  # bottom-center
        ox, oy = (w - region_w) // 2, h - region_h - margin

    # duración total del video
    dur = _probe_duration(ffmpeg, final_video)
    n_frames = max(1, round(dur * fps))
    env = _voice_envelope(audio_path, ffmpeg, fps, n_frames)

    # Un solo pase: el video final + los frames RGBA de la mascota por stdin
    # (rawvideo = alpha perfecta, sin códec intermedio que la pierda). El
    # overlay usa el canal alpha para que solo se vea la mascota, no un recuadro.
    proc = subprocess.Popen(
        [ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
         "-i", str(final_video),
         "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{region_w}x{region_h}", "-r", str(fps),
         "-i", "pipe:0",
         "-filter_complex", f"[0:v][1:v]overlay={ox}:{oy}:format=auto:eof_action=pass[v]",
         "-map", "[v]", "-map", "0:a?", "-t", f"{dur:.3f}",
         *encode_args, str(dest)],
        stdin=subprocess.PIPE,
    )
    try:
        for i in range(n_frames):
            t = i / fps
            action = action_at(segments, t)
            # lip-sync: durante 'talk', si la voz calla -> idle (boca cerrada)
            ni = int((t - intro_offset) * fps)
            speaking = 0 <= ni < n_frames and env[ni] >= voice_threshold
            if action == TALK and not speaking:
                action = IDLE
            frames = actions.get(action) or actions[IDLE]
            fr = frames[int(t * mascot_fps) % len(frames)]
            canvas_img = Image.new("RGBA", (region_w, region_h), (0, 0, 0, 0))
            # anclar abajo-centro del region (pies al piso)
            canvas_img.alpha_composite(fr, ((region_w - fr.width) // 2, region_h - fr.height))
            proc.stdin.write(np.asarray(canvas_img, np.uint8).tobytes())
        proc.stdin.close()
        if proc.wait() != 0:
            raise MascotAssetsError("ffmpeg falló componiendo la mascota")
    finally:
        if proc.poll() is None:
            proc.kill()
    logger.info("Mascota compuesta (%s, %d frames)", position, n_frames)
    return dest


def _probe_duration(ffmpeg: str, source: Path) -> float:
    ffprobe = str(Path(ffmpeg).parent / "ffprobe.exe") if ("\\" in ffmpeg or "/" in ffmpeg) else "ffprobe"
    out = subprocess.run(
        [ffprobe, "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(source)],
        capture_output=True, text=True,
    ).stdout.strip()
    return float(out) if out else 0.0
