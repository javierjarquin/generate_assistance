"""Ensamblador ffmpeg: Ken Burns + overlays animados + xfade variado + subtítulos
ASS + grading global + mezcla de audio con ducking.

Detección de encoder por hardware portada de shorts-factory. Canvas
configurable: 1920x1080 (YouTube) o 1080x1920 (Shorts/Reels).
"""

import logging
import subprocess
from pathlib import Path

from illustrated_narrator.ports.video_assembler import VideoAssemblerPort

logger = logging.getLogger(__name__)

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

# Transiciones xfade rotadas por índice: variedad sin decidir a mano
_TRANSITIONS = ("fade", "wipeleft", "circleopen", "slideleft", "fadeblack", "wiperight")

# Pan alternado para las tomas de un mismo plano: la 2ª contrasta con la 1ª
_SHOT_PAN_POOL = ("zoom-in-center", "zoom-out-center", "pan-right", "pan-left", "zoom-in-top-right")


def _shot_pan_cycle(base: str, n: int) -> list[str]:
    """Movimientos de cámara para las n tomas: la primera respeta el base,
    las siguientes alternan para que cada corte se sienta distinto."""
    if n == 1:
        return [base]
    pans = [base]
    for i in range(1, n):
        pans.append(_SHOT_PAN_POOL[i % len(_SHOT_PAN_POOL)])
    return pans

# Acabado global: contraste/saturación leves + viñeta + grano fino
_GRADING = "eq=saturation=1.08:contrast=1.05,vignette=PI/4.6,noise=alls=6:allf=t"

_HARD_CUT = 0.05  # transición casi-seca para los primeros 5s (sin dissolve)
_HARD_CUT_WINDOW = 5.0


def _xfd_at(offset: float, xfade_duration: float) -> float:
    """Corte seco dentro de la ventana inicial; xfade normal después."""
    return _HARD_CUT if offset < _HARD_CUT_WINDOW else xfade_duration


def _xfd_sequence(durations: list[float], xfade_duration: float) -> list[float]:
    """xfd de cada una de las n-1 transiciones (corto dentro de la ventana inicial)."""
    xfds: list[float] = []
    running_offset = durations[0] - xfade_duration if durations else 0.0
    for i in range(1, len(durations)):
        xfd = _xfd_at(running_offset, xfade_duration)
        xfds.append(xfd)
        running_offset += durations[i] - xfd
    return xfds


def chained_duration(durations: list[float], xfade_duration: float) -> float:
    """Duración del video tras encadenar clips con xfade variable (corto al
    inicio). Fuente única de verdad para -t del render y para el inicio del CTA."""
    if not durations:
        return 0.0
    return sum(durations) - sum(_xfd_sequence(durations, xfade_duration))


def _overlay_chain(kind: str, w: int, h: int, fps: int) -> tuple[str, str] | None:
    """(fuente lavfi, cadena de mezcla) para el overlay animado, o None."""
    if kind in ("niebla", "fog", "humo"):
        src = (
            f"nullsrc=s={w}x{h}:r={fps},noise=alls=70:allf=t,"
            "boxblur=24:3,scroll=h=0.0018,format=gray"
        )
        blend = "blend=all_mode=screen:all_opacity=0.14"
    elif kind in ("polvo", "dust", "particulas", "partículas"):
        src = (
            f"nullsrc=s={w}x{h}:r={fps},noise=alls=100:allf=t,"
            "eq=brightness=-0.42:contrast=6,boxblur=1:1,scroll=v=-0.004,format=gray"
        )
        blend = "blend=all_mode=screen:all_opacity=0.20"
    elif kind in ("lluvia", "rain"):
        src = (
            f"nullsrc=s={w}x{int(h / 5)}:r={fps},noise=alls=45:allf=t,"
            f"eq=brightness=-0.35:contrast=5,scale={w}:{h},scroll=v=0.45,format=gray"
        )
        blend = "blend=all_mode=screen:all_opacity=0.16"
    elif kind in ("burbujas", "bubbles", "submarino"):
        src = (
            f"nullsrc=s={w}x{h}:r={fps},noise=alls=90:allf=t,"
            "eq=brightness=-0.45:contrast=7,boxblur=2:1,scroll=v=-0.010,format=gray"
        )
        blend = "blend=all_mode=screen:all_opacity=0.17"
    else:
        return None
    return src, blend


class FFmpegAssembler(VideoAssemblerPort):
    def __init__(
        self,
        ffmpeg_path: str = "ffmpeg",
        encoder: str = "auto",
        fps: int = 30,
        canvas: tuple[int, int] = (1920, 1080),
    ) -> None:
        self._ffmpeg = ffmpeg_path
        self._encoder = encoder
        self._fps = fps
        self._canvas_w, self._canvas_h = canvas
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
        args = ["-c:v", encoder, "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart"]
        if encoder == "libx264":
            args += ["-preset", "veryfast", "-crf", "23"]
        else:
            args += ["-b:v", "8M"]
        return args

    # ------------------------------------------------------------ clips

    def render_plano_clip(
        self,
        image_paths: list[Path],
        duration_seconds: float,
        pan_direction: str,
        dest: Path,
        overlay: str | None = None,
        motion=None,
    ) -> Path:
        """Clip de un plano. Con varias imágenes, se reparten la duración con
        cortes secos (una imagen fija > ~4s se siente estática y pierde al
        espectador; cambiar de toma sostiene la atención). `motion` es un
        MotionProfile (o su nombre) que fija la energía del Ken Burns."""
        dest.parent.mkdir(parents=True, exist_ok=True)
        images = [p for p in image_paths if p and Path(p).exists()]
        if not images:
            raise ValueError("render_plano_clip necesita al menos una imagen")

        if len(images) == 1:
            return self._render_shot(
                images[0], duration_seconds, pan_direction, dest, overlay, motion
            )

        # Reparte la duración en tomas ~iguales, alterna el sentido del Ken Burns
        n = len(images)
        each = duration_seconds / n
        shot_pans = _shot_pan_cycle(pan_direction, n)
        temp_clips: list[Path] = []
        for i, img in enumerate(images):
            temp = dest.with_name(f"{dest.stem}__shot{i}.mp4")
            self._render_shot(img, each, shot_pans[i], temp, overlay, motion)
            temp_clips.append(temp)
        try:
            self._concat(temp_clips, dest)
        finally:
            for t in temp_clips:
                t.unlink(missing_ok=True)
        return dest

    def _render_shot(
        self,
        image_path: Path,
        duration_seconds: float,
        pan_direction: str,
        dest: Path,
        overlay: str | None,
        motion,
    ) -> Path:
        from illustrated_narrator.domain.services.motion_profile import profile_by_name

        profile = motion if hasattr(motion, "zoom_per_frame") else profile_by_name(str(motion))
        dest.parent.mkdir(parents=True, exist_ok=True)
        w, h = self._canvas_w, self._canvas_h
        variant = _PAN_VARIANTS.get(pan_direction, _PAN_VARIANTS["zoom-in-center"])
        frames = max(2, round(duration_seconds * self._fps))
        x_expr = variant["x"].format(total_frames=frames)
        y_expr = variant["y"].format(total_frames=frames)

        # Zoom construido desde el perfil: la velocidad marca la energía. Con
        # punch-in, los primeros ~0.3s caen desde una escala mayor (golpe de
        # entrada que "despierta" al scroller) y luego el zoom continúa.
        pf = max(1, round(0.3 * self._fps))
        zpf, maxz, punch = profile.zoom_per_frame, profile.max_zoom, profile.punch_in
        if punch > 0:
            z_expr = (
                f"if(lt(on,{pf}),{1 + punch:.3f}-{punch:.3f}*on/{pf},"
                f"min(zoom+{zpf:.4f},{maxz:.2f}))"
            )
        else:
            z_expr = f"min(zoom+{zpf:.4f},{maxz:.2f})"

        parts = [
            "[0:v]split=2[bg][fg]",
            f"[bg]scale={w}:{h}:force_original_aspect_ratio=increase,"
            f"crop={w}:{h},gblur=sigma=20,eq=brightness=-0.1[bg]",
            f"[fg]scale={w}:{h}:force_original_aspect_ratio=decrease,"
            "pad=ceil(iw/2)*2:ceil(ih/2)*2[fg]",
            "[bg][fg]overlay=(W-w)/2:(H-h)/2,format=yuv420p[composited]",
            f"[composited]scale={w * 2}:{h * 2}:flags=lanczos,"
            f"zoompan=z='{z_expr}':x='{x_expr}':y='{y_expr}':"
            f"d={frames}:s={w}x{h}:fps={self._fps}[kb]",
        ]
        current = "[kb]"
        inputs = ["-loop", "1", "-i", str(image_path)]

        if overlay in ("fuego", "fire", "llamas"):
            # Parpadeo cálido: la propia imagen pulsa como iluminada por llamas
            parts.append(
                f"{current}eq=brightness='0.02*sin(9*t)+0.014*sin(23*t)':"
                "saturation=1.06[flick]"
            )
            current = "[flick]"
        else:
            chain = _overlay_chain(overlay or "", w, h, self._fps) if overlay else None
            if chain:
                src, blend = chain
                inputs += ["-f", "lavfi", "-t", f"{duration_seconds:.3f}", "-i", src]
                parts.append(f"[1:v]format=yuv420p[ov]")
                parts.append(f"{current}[ov]{blend}[mixed]")
                current = "[mixed]"

        if profile.shake_px > 0:
            s = profile.shake_px
            m = s + 2  # margen de recorte para que la sacudida no muestre bordes
            parts.append(
                f"{current}crop=w=iw-{2 * m}:h=ih-{2 * m}:"
                f"x='{m}+{s}*sin(52*t)':y='{m}+{s}*cos(41*t)',"
                f"scale={w}:{h}[shaken]"
            )
            current = "[shaken]"

        parts.append(f"{current}format=yuv420p[vout]")
        self._run(
            [
                *inputs,
                "-t", f"{duration_seconds:.3f}",
                "-filter_complex", ";".join(parts),
                "-map", "[vout]",
                "-t", f"{duration_seconds:.3f}",
                *self._encode_args(),
                str(dest),
            ]
        )
        return dest

    def _concat(self, clips: list[Path], dest: Path) -> None:
        """Une clips con corte seco (concat demuxer, sin re-encode)."""
        listing = dest.with_name(f"{dest.stem}__concat.txt")
        listing.write_text(
            "".join(f"file '{c.resolve().as_posix()}'\n" for c in clips), encoding="utf-8"
        )
        try:
            self._run(
                ["-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(dest)]
            )
        finally:
            listing.unlink(missing_ok=True)

    def render_end_card(self, text: str, duration_seconds: float, dest: Path) -> Path:
        """Tarjeta CTA de cierre: fondo oscuro con leve zoom + texto (vía ASS aparte)."""
        dest.parent.mkdir(parents=True, exist_ok=True)
        w, h = self._canvas_w, self._canvas_h
        self._run(
            [
                "-f", "lavfi",
                "-i", f"color=c=0x0d0d12:s={w}x{h}:d={duration_seconds:.3f}:r={self._fps}",
                "-vf", "format=yuv420p,fade=t=in:d=0.3",
                "-t", f"{duration_seconds:.3f}",
                *self._encode_args(),
                str(dest),
            ]
        )
        return dest

    # --------------------------------------------------------- ensamble

    def assemble(
        self,
        clip_paths: list[Path],
        ass_subtitle_path: Path | None,
        audio_path: Path,
        dest: Path,
        xfade_duration: float = 0.5,
        bed_path: Path | None = None,
    ) -> Path:
        if not clip_paths:
            raise ValueError("assemble() necesita al menos un clip")
        dest.parent.mkdir(parents=True, exist_ok=True)

        durations = [_probe_duration(self._ffmpeg, p) for p in clip_paths]
        inputs: list[str] = []
        for p in clip_paths:
            inputs += ["-i", str(p)]

        # Estándar de retención: nada de dissolves en los primeros 5s — ahí se
        # decide la permanencia. Las primeras transiciones son cortes casi
        # secos; después entran los xfade variados. Secuencia calculada por la
        # función compartida para que el CTA y el -t cuadren.
        xfds = _xfd_sequence(durations, xfade_duration)
        filter_lines: list[str] = []
        if len(clip_paths) == 1:
            video_label = "0:v"
        else:
            running_offset = durations[0] - xfds[0]
            prev_label = "0:v"
            for i in range(1, len(clip_paths)):
                out_label = f"v{i}"
                xfd = xfds[i - 1]
                # Corte seco = fade brevísimo; xfade variado solo pasados los 5s
                transition = "fade" if xfd == _HARD_CUT else _TRANSITIONS[(i - 1) % len(_TRANSITIONS)]
                filter_lines.append(
                    f"[{prev_label}][{i}:v]xfade=transition={transition}:"
                    f"duration={xfd:.3f}:offset={running_offset:.3f}[{out_label}]"
                )
                prev_label = out_label
                if i < len(clip_paths):
                    running_offset += durations[i] - (xfds[i] if i < len(xfds) else 0.0)
            video_label = prev_label

        # Grading global antes de subtítulos (el texto no debe granularse)
        filter_lines.append(f"[{video_label}]{_GRADING}[graded]")
        video_label = "graded"

        if ass_subtitle_path is not None and ass_subtitle_path.exists():
            escaped = str(ass_subtitle_path).replace("\\", "/").replace(":", "\\:")
            filter_lines.append(f"[{video_label}]ass='{escaped}'[vout]")
            video_label = "vout"

        narr_index = len(clip_paths)
        args = [*inputs, "-i", str(audio_path)]

        # Duración total del video tras encadenar (cada transición solapa su
        # propio xfd — corto al inicio, xfade normal después). La narración se
        # rellena con silencio hasta cubrir la tarjeta de cierre.
        video_total = chained_duration(durations, xfade_duration)

        # loudnorm a -14 LUFS: estándar de YouTube/Shorts. Sin esto el audio
        # sale muy bajo (nuestra narración salía a -34 LUFS medios) y el video
        # se siente flojo frente al resto del feed -> el usuario hace scroll.
        if bed_path is not None and bed_path.exists():
            bed_index = narr_index + 1
            args += ["-i", str(bed_path)]
            # 1. Aplicamos apad y lo mandamos a una etiqueta temporal
            filter_lines.append(f"[{narr_index}:a]apad[narrpad_raw]")
            # 2. Duplicamos el flujo en dos copias independientes
            filter_lines.append("[narrpad_raw]asplit[narrpad1][narrpad2]")
            # 3. Usamos la primera copia para el sidechain compress
            filter_lines.append(
                f"[{bed_index}:a][narrpad1]"
                "sidechaincompress=threshold=0.04:ratio=12:attack=60:release=500[duck]"
            )
            # 4. Mezclamos la segunda copia con el audio comprimido
            filter_lines.append(
                f"[narrpad2][duck]amix=inputs=2:duration=first:normalize=0,"
                "loudnorm=I=-14:TP=-1.5:LRA=11[aout]"
            )
            audio_map = "[aout]"
        else:
            filter_lines.append(
                f"[{narr_index}:a]apad,loudnorm=I=-14:TP=-1.5:LRA=11[aout]"
            )
            audio_map = "[aout]"

        args += ["-filter_complex", ";".join(filter_lines)]
        args += ["-map", f"[{video_label}]" if not video_label.endswith(":v") else video_label]
        args += ["-map", audio_map, "-t", f"{video_total:.3f}", *self._encode_args(), str(dest)]

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
