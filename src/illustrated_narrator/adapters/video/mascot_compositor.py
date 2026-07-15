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
    WALK,
    MascotSegment,
    segment_at,
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

    sprite_w = max(fr.width for frs in actions.values() for fr in frs)
    region_h = max(fr.height for frs in actions.values() for fr in frs)
    # La mascota se DESPLAZA al caminar (entra a cuadro, pasea): la region se
    # ensancha `travel` px para dar cancha al recorrido sin salirse. En reposo
    # la mascota queda anclada al lado de la esquina (misma posición de siempre).
    walks = any(s.action == WALK for s in segments)
    travel = int(w * 0.16) if walks else 0
    region_w = sprite_w + travel
    margin = int(h * 0.02)
    oy = h - region_h - margin
    if position == "bottom-right":
        ox = w - region_w - margin
        rest_cx = region_w - sprite_w / 2.0   # pegada a la derecha del region
        inner_sign = -1.0                     # el interior del cuadro queda a la izq.
    elif position == "bottom-left":
        ox = margin
        rest_cx = sprite_w / 2.0
        inner_sign = 1.0
    else:  # bottom-center
        ox = (w - region_w) // 2
        rest_cx = region_w / 2.0
        inner_sign = -1.0

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
    # Antes del primer segmento la mascota aún no está en escena: se oculta
    # (cuadro transparente) para que haga su ENTRADA caminando y no aparezca
    # pegada en la esquina durante la intro/pre-rollo.
    first_start = segments[0].start if segments else 0.0
    blank = np.zeros((region_h, region_w, 4), np.uint8).tobytes()
    try:
        for i in range(n_frames):
            t = i / fps
            if t < first_start:
                proc.stdin.write(blank)
                continue
            seg = segment_at(segments, t)
            action = seg.action if seg is not None else IDLE
            # lip-sync: durante 'talk', si la voz calla -> idle (boca cerrada)
            ni = int((t - intro_offset) * fps)
            speaking = 0 <= ni < n_frames and env[ni] >= voice_threshold
            if action == TALK and not speaking:
                action = IDLE
            frames = actions.get(action) or actions[IDLE]
            fr = frames[int(t * mascot_fps) % len(frames)]
            # centro X: reposo salvo al caminar, que traslada a la mascota.
            cx = rest_cx
            if seg is not None and action == WALK and travel:
                span = max(seg.end - seg.start, 1e-6)
                p = min(max((t - seg.start) / span, 0.0), 1.0)
                if seg.variant == "pace":     # ida y vuelta: no teletransporta
                    cx = rest_cx + inner_sign * travel * 0.7 * (1.0 - abs(2.0 * p - 1.0))
                else:                          # "in": entra desde el interior a su sitio
                    cx = rest_cx + inner_sign * travel * (1.0 - p)
            canvas_img = Image.new("RGBA", (region_w, region_h), (0, 0, 0, 0))
            # anclar por los pies (abajo), centrado en cx; clamp para que el
            # sprite nunca se salga del region (alpha_composite exige dest>=0).
            px = min(max(int(cx - fr.width / 2.0), 0), region_w - fr.width)
            canvas_img.alpha_composite(fr, (px, region_h - fr.height))
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
