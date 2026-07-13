"""Ensamblador ffmpeg: Ken Burns por plano + xfade entre clips + subtítulos ASS.

Detección de encoder por hardware portada de shorts-factory (mismo build de
ffmpeg, mismo GPU AMD -> h264_amf en esta máquina).
"""

import logging
import subprocess
from pathlib import Path

from illustrated_narrator.ports.video_assembler import VideoAssemblerPort

logger = logging.getLogger(__name__)

# Variantes de Ken Burns: zoom/pan expresados en las variables nativas de zoompan
# (iw/ih = tamaño de entrada, zoom = factor actual, on = numero de frame de salida).
# "d" (frames totales) NO es una variable evaluable dentro de x/y/z en este build
# de ffmpeg -- solo existe como opcion del filtro -- por eso las variantes de pan
# usan "{total_frames}" como placeholder, sustituido por el numero real de frames
# al construir el filtro (ver _pan_expr).
_PAN_VARIANTS: dict[str, dict[str, str]] = {
    "zoom-in-center": {
        "z": "min(zoom+0.0015,1.3)", "x": "iw/2-(iw/zoom/2)", "y": "ih/2-(ih/zoom/2)",
    },
    "zoom-in-top-right": {
        "z": "min(zoom+0.0015,1.3)", "x": "iw-(iw/zoom)", "y": "0",
    },
    "zoom-in-bottom-left": {
        "z": "min(zoom+0.0015,1.3)", "x": "0", "y": "ih-(ih/zoom)",
    },
    "zoom-out-center": {
        "z": "if(eq(on,0),1.3,max(1.001,zoom-0.0015))", "x": "iw/2-(iw/zoom/2)", "y": "ih/2-(ih/zoom/2)",
    },
    "pan-right": {
        "z": "1.15", "x": "(iw-iw/zoom)*(on/({total_frames}-1))", "y": "ih/2-(ih/zoom/2)",
    },
    "pan-left": {
        "z": "1.15", "x": "(iw-iw/zoom)*(1-on/({total_frames}-1))", "y": "ih/2-(ih/zoom/2)",
    },
}

_CANVAS_W, _CANVAS_H = 1920, 1080


class FFmpegAssembler(VideoAssemblerPort):
    def __init__(self, ffmpeg_path: str = "ffmpeg", encoder: str = "auto", fps: int = 30) -> None:
        self._ffmpeg = ffmpeg_path
        self._encoder = encoder
        self._fps = fps
        self._resolved_encoder: str | None = None

    def _run(self, args: list[str]) -> None:
        cmd = [self._ffmpeg, "-hide_banner", "-y", *args]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg falló ({result.returncode}): {result.stderr[-1200:]}")

    def _pick_encoder(self) -> str:
        if self._resolved_encoder:
            return self._resolved_encoder
        if self._encoder != "auto":
            self._resolved_encoder = self._encoder
            return self._encoder
        for candidate in ("h264_nvenc", "h264_amf", "h264_qsv"):
            probe = subprocess.run(
                [
                    self._ffmpeg, "-hide_banner", "-loglevel", "error", "-f", "lavfi",
                    "-i", "testsrc2=duration=0.1:size=256x256:rate=30",
                    "-frames:v", "1", "-c:v", candidate, "-f", "null", "-",
                ],
                capture_output=True, text=True,
            )
            if probe.returncode == 0:
                logger.info("Encoder de video: %s (hardware)", candidate)
                self._resolved_encoder = candidate
                return candidate
        logger.info("Encoder de video: libx264 (CPU)")
        self._resolved_encoder = "libx264"
        return "libx264"

    def _encode_args(self) -> list[str]:
        encoder = self._pick_encoder()
        args = ["-c:v", encoder, "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart"]
        if encoder == "libx264":
            args += ["-preset", "veryfast", "-crf", "23"]
        else:
            args += ["-b:v", "6M"]
        return args

    def render_plano_clip(
        self, image_path: Path, duration_seconds: float, pan_direction: str, dest: Path
    ) -> Path:
        dest.parent.mkdir(parents=True, exist_ok=True)
        variant = _PAN_VARIANTS.get(pan_direction, _PAN_VARIANTS["zoom-in-center"])
        frames = max(2, round(duration_seconds * self._fps))
        x_expr = variant["x"].format(total_frames=frames)
        y_expr = variant["y"].format(total_frames=frames)
        z_expr = variant["z"].format(total_frames=frames)
        filter_complex = (
            "[0:v]split=2[bg][fg];"
            f"[bg]scale={_CANVAS_W}:{_CANVAS_H}:force_original_aspect_ratio=increase,"
            f"crop={_CANVAS_W}:{_CANVAS_H},gblur=sigma=20,eq=brightness=-0.1[bg];"
            f"[fg]scale={_CANVAS_W}:{_CANVAS_H}:force_original_aspect_ratio=decrease,"
            "pad=ceil(iw/2)*2:ceil(ih/2)*2[fg];"
            "[bg][fg]overlay=(W-w)/2:(H-h)/2,format=yuv420p[composited];"
            f"[composited]scale={_CANVAS_W * 2}:{_CANVAS_H * 2}:flags=lanczos,"
            f"zoompan=z='{z_expr}':x='{x_expr}':y='{y_expr}':"
            f"d={frames}:s={_CANVAS_W}x{_CANVAS_H}:fps={self._fps},format=yuv420p[vout]"
        )
        self._run(
            [
                "-loop", "1", "-i", str(image_path), "-t", f"{duration_seconds:.3f}",
                "-filter_complex", filter_complex, "-map", "[vout]",
                "-t", f"{duration_seconds:.3f}",
                *self._encode_args(),
                str(dest),
            ]
        )
        return dest

    def assemble(
        self,
        clip_paths: list[Path],
        ass_subtitle_path: Path | None,
        audio_path: Path,
        dest: Path,
        xfade_duration: float = 0.5,
    ) -> Path:
        if not clip_paths:
            raise ValueError("assemble() necesita al menos un clip")
        dest.parent.mkdir(parents=True, exist_ok=True)

        durations = [_probe_duration(self._ffmpeg, p) for p in clip_paths]
        inputs: list[str] = []
        for p in clip_paths:
            inputs += ["-i", str(p)]

        if len(clip_paths) == 1:
            video_label = "0:v"
        else:
            chain_parts = []
            running_offset = durations[0] - xfade_duration
            prev_label = "0:v"
            for i in range(1, len(clip_paths)):
                out_label = f"v{i}" if i < len(clip_paths) - 1 else "vout_pre"
                chain_parts.append(
                    f"[{prev_label}][{i}:v]xfade=transition=fade:duration={xfade_duration:.3f}:"
                    f"offset={running_offset:.3f}[{out_label}]"
                )
                prev_label = out_label
                running_offset += durations[i] - xfade_duration
            video_label = prev_label

        filter_lines = []
        if len(clip_paths) > 1:
            filter_lines.extend(chain_parts)
        if ass_subtitle_path is not None and ass_subtitle_path.exists():
            escaped = str(ass_subtitle_path).replace("\\", "/").replace(":", "\\:")
            filter_lines.append(f"[{video_label}]ass='{escaped}'[vout]")
            final_label = "vout"
        else:
            final_label = video_label

        filter_complex = ";".join(filter_lines) if filter_lines else None
        audio_input_index = len(clip_paths)

        args = [*inputs, "-i", str(audio_path)]
        if filter_complex:
            args += ["-filter_complex", filter_complex, "-map", f"[{final_label}]"]
        else:
            args += ["-map", f"{final_label}"]
        args += ["-map", f"{audio_input_index}:a", "-shortest", *self._encode_args(), str(dest)]

        self._run(args)
        return dest


def _probe_duration(ffmpeg_path: str, source: Path) -> float:
    ffprobe = str(Path(ffmpeg_path).parent / "ffprobe.exe") if "\\" in ffmpeg_path or "/" in ffmpeg_path else "ffprobe"
    result = subprocess.run(
        [
            ffprobe, "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(source),
        ],
        capture_output=True, text=True,
    )
    try:
        return float(result.stdout.strip())
    except ValueError as exc:
        raise RuntimeError(f"No se pudo obtener duración de {source}: {result.stderr}") from exc
