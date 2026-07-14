"""Parallax 2.5D: convierte una imagen fija en un plano con movimiento de
cámara con profundidad — el frente se desplaza más que el fondo, dando
sensación 3D (mucho más vivo que un Ken Burns plano).

Cómo: con el mapa de profundidad se hace un warp por-pixel (cv2.remap). La
cámara recorre una trayectoria suave; cada pixel se desplaza proporcional a su
cercanía. Un zoom base garantiza que siempre se muestree dentro de la imagen
(sin bordes negros). Los frames se envían crudos a ffmpeg por stdin.

CPU-only, ~1-2s por segundo de clip. Si falta la profundidad, el ensamblador
usa el Ken Burns clásico.
"""

import logging
import math
import subprocess

logger = logging.getLogger(__name__)

# Parámetros de parallax por perfil de movimiento: amplitud lateral (frac. del
# ancho), amplitud vertical y zoom base. Impacto = cámara más agresiva.
_PARALLAX_BY_MOTION = {
    "calm": dict(amp_x=0.010, amp_y=0.006, zoom=1.06, depth=0.55),
    "normal": dict(amp_x=0.018, amp_y=0.010, zoom=1.08, depth=0.75),
    "energetic": dict(amp_x=0.030, amp_y=0.016, zoom=1.11, depth=1.05),
    "impact": dict(amp_x=0.045, amp_y=0.024, zoom=1.15, depth=1.40),
}


def render_parallax_clip(
    ffmpeg_path: str,
    encode_args: list[str],
    image_path,
    depth,
    duration_seconds: float,
    fps: int,
    canvas: tuple[int, int],
    dest,
    motion_name: str = "normal",
) -> None:
    """Renderiza el clip de parallax de una toma. `depth` es HxW float 0..1."""
    import cv2
    import numpy as np

    w, h = canvas
    params = _PARALLAX_BY_MOTION.get(motion_name, _PARALLAX_BY_MOTION["normal"])

    # Imagen a lienzo (cubrir, recorte centrado) para trabajar a resolución final
    bgr = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    bgr = _cover(bgr, w, h, cv2)
    depth = cv2.resize(depth, (w, h), interpolation=cv2.INTER_CUBIC)
    # Suavizar la profundidad evita bordes duros/estiramientos feos en el warp
    depth = cv2.GaussianBlur(depth, (0, 0), sigmaX=w * 0.006)
    # Desplazamiento proporcional a la CERCANÍA (near=1 se mueve el máximo, far=0
    # casi nada): parallax natural. La trayectoria (sin) sale y vuelve a 0, así
    # que no hay deriva aunque el desplazamiento sea siempre en un sentido.
    disp = depth * params["depth"]

    base_x, base_y = np.meshgrid(
        np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32)
    )
    zoom = params["zoom"]
    amp_x = params["amp_x"] * w
    amp_y = params["amp_y"] * h
    total_frames = max(2, round(duration_seconds * fps))

    proc = subprocess.Popen(
        [
            ffmpeg_path, "-hide_banner", "-loglevel", "error", "-y",
            "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{w}x{h}", "-r", str(fps),
            "-i", "pipe:0",
            "-t", f"{duration_seconds:.3f}",
            *encode_args, str(dest),
        ],
        stdin=subprocess.PIPE,
    )
    try:
        cx, cy = w / 2.0, h / 2.0
        for n in range(total_frames):
            t = n / max(total_frames - 1, 1)
            # Trayectoria: órbita suave (elíptica) — evita el "vaivén" plano
            phase = t * 2.0 * math.pi
            off_x = amp_x * math.sin(phase * 0.5)
            off_y = amp_y * math.sin(phase * 0.5 + math.pi / 2)
            # Desplazamiento por profundidad (near se mueve más) + zoom base
            map_x = cx + (base_x - cx) / zoom - off_x * disp
            map_y = cy + (base_y - cy) / zoom - off_y * disp
            frame = cv2.remap(
                bgr, map_x, map_y, interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT
            )
            proc.stdin.write(frame.astype(np.uint8).tobytes())
        proc.stdin.close()
        ret = proc.wait()
        if ret != 0:
            raise RuntimeError(f"ffmpeg (parallax) terminó con código {ret}")
    finally:
        if proc.poll() is None:
            proc.kill()
    logger.info("Parallax %s (%d frames, motion=%s)", dest.name, total_frames, motion_name)


def _cover(bgr, w: int, h: int, cv2):
    """Escala y recorta la imagen para cubrir el lienzo (sin bordes)."""
    ih, iw = bgr.shape[:2]
    scale = max(w / iw, h / ih)
    nw, nh = int(math.ceil(iw * scale)), int(math.ceil(ih * scale))
    resized = cv2.resize(bgr, (nw, nh), interpolation=cv2.INTER_CUBIC)
    x0 = (nw - w) // 2
    y0 = (nh - h) // 2
    return resized[y0:y0 + h, x0:x0 + w]
