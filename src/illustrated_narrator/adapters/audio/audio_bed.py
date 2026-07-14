"""Cama de audio: música de fondo + SFX por plano + whoosh en transiciones.

Prioridad de fuentes:
1. Archivos reales del usuario en projects/<slug>/assets/ (music.mp3|wav,
   sfx/<nombre>.wav) — si existen, se usan.
2. Generación procedural con ffmpeg (lavfi): pad ambiental para música y
   texturas de ruido moldeado para olas/fuego/viento/retumbe. Crudo pero
   funcional; el usuario puede reemplazar con archivos reales sin tocar código.

La cama se mezcla aparte (bed.wav) y el ensamblador la agrega con ducking
(sidechaincompress) bajo la narración.
"""

import logging
import subprocess
from pathlib import Path

from illustrated_narrator.domain.entities.plano import Plano
from illustrated_narrator.domain.services.sfx_taxonomy import sfx_kind as _sfx_kind

logger = logging.getLogger(__name__)


class AudioBedBuilder:
    def __init__(self, ffmpeg_path: str = "ffmpeg", music_volume: float = 0.22) -> None:
        self._ffmpeg = ffmpeg_path
        self._music_volume = music_volume

    def _run(self, args: list[str]) -> None:
        cmd = [self._ffmpeg, "-hide_banner", "-loglevel", "error", "-y", *args]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg (audio bed) falló: {result.stderr[-600:]}")

    # ------------------------------------------------------- generadores

    def _music_source(self, assets_dir: Path, duration: float, cache_dir: Path) -> Path:
        # Cualquier contenedor con audio sirve (ffmpeg extrae la pista): mp3,
        # wav, m4a, ogg, e incluso un mp4/mkv (p. ej. una descarga de música).
        for stem in ("music", "musica"):
            for ext in ("mp3", "wav", "m4a", "ogg", "opus", "flac", "aac", "mp4", "mkv", "webm"):
                candidate = assets_dir / f"{stem}.{ext}"
                if candidate.exists():
                    return candidate
        dest = cache_dir / "music_auto.wav"
        # Pad ambiental: acorde menor con desafinación leve, trémolo lento y
        # eco — tono documental sobrio. Sustituible por assets/music.mp3.
        self._run(
            [
                "-f", "lavfi",
                "-i", f"sine=frequency=110:duration={duration:.2f}",
                "-f", "lavfi",
                "-i", f"sine=frequency=130.8:duration={duration:.2f}",
                "-f", "lavfi",
                "-i", f"sine=frequency=164.4:duration={duration:.2f}",
                "-f", "lavfi",
                "-i", f"anoisesrc=colour=brown:amplitude=0.03:duration={duration:.2f}",
                "-filter_complex",
                "[0:a][1:a][2:a][3:a]amix=inputs=4:normalize=1,"
                "tremolo=f=0.13:d=0.35,aecho=0.7:0.5:520:0.28,"
                "lowpass=f=900,afade=t=in:d=2.5,"
                f"afade=t=out:st={max(duration - 3.0, 0):.2f}:d=3.0[out]",
                "-map", "[out]",
                str(dest),
            ]
        )
        return dest

    def _sfx_source(self, kind: str, duration: float, cache_dir: Path, assets_dir: Path) -> Path:
        for ext in ("wav", "mp3"):
            candidate = assets_dir / "sfx" / f"{kind}.{ext}"
            if candidate.exists():
                return candidate
        dest = cache_dir / f"sfx_{kind}_{int(duration)}.wav"
        if dest.exists():
            return dest
        d = f"{duration:.2f}"
        recipes = {
            # olas: ruido marrón con vaivén lento
            "waves": f"anoisesrc=colour=brown:amplitude=0.5:duration={d},"
                     "lowpass=f=600,tremolo=f=0.18:d=0.8",
            # fuego: ruido rosa con parpadeo rápido e irregular (doble trémolo)
            "fire": f"anoisesrc=colour=pink:amplitude=0.4:duration={d},"
                    "highpass=f=800,tremolo=f=9:d=0.6,tremolo=f=2.3:d=0.5",
            # retumbe: seno grave + ruido marrón, ataque brusco
            "rumble": f"anoisesrc=colour=brown:amplitude=0.9:duration={d},"
                      "lowpass=f=120,tremolo=f=6:d=0.4,afade=t=in:d=0.15",
            # viento: ruido rosa filtrado con vaivén medio
            "wind": f"anoisesrc=colour=pink:amplitude=0.35:duration={d},"
                    "lowpass=f=1400,highpass=f=250,tremolo=f=0.4:d=0.7",
            # burbujas: ruido blanco agudo pulsado
            "bubbles": f"anoisesrc=colour=white:amplitude=0.22:duration={d},"
                       "highpass=f=2200,tremolo=f=11:d=0.9,lowpass=f=6000",
        }
        self._run(["-f", "lavfi", "-i", recipes[kind], str(dest)])
        return dest

    def _whoosh_source(self, cache_dir: Path) -> Path:
        dest = cache_dir / "sfx_whoosh.wav"
        if not dest.exists():
            self._run(
                [
                    "-f", "lavfi",
                    "-i", "anoisesrc=colour=pink:amplitude=0.8:duration=0.5",
                    "-af", "highpass=f=400,lowpass=f=4000,afade=t=in:d=0.18,afade=t=out:st=0.2:d=0.3",
                    str(dest),
                ]
            )
        return dest

    # ------------------------------------------------------------- build

    def build(
        self,
        planos: list[Plano],
        duration: float,
        assets_dir: Path,
        cache_dir: Path,
        transition_times: list[float] | None = None,
        dest: Path | None = None,
    ) -> Path:
        """Mezcla música + sfx de planos + whooshes. Devuelve la ruta del bed."""
        cache_dir.mkdir(parents=True, exist_ok=True)
        dest = dest or cache_dir / "bed.wav"

        inputs: list[str] = []
        filters: list[str] = []
        labels: list[str] = []
        idx = 0

        music = self._music_source(assets_dir, duration, cache_dir)
        inputs += ["-i", str(music)]
        filters.append(f"[{idx}:a]volume={self._music_volume},apad=whole_dur={duration:.2f}[m]")
        labels.append("[m]")
        idx += 1

        for plano in planos:
            if not plano.audio.sfx or plano.inicio_real_seg is None:
                continue
            kind = _sfx_kind(plano.audio.sfx)
            if kind is None:
                logger.info("SFX sin generador para '%s' (plano %s)", plano.audio.sfx, plano.id)
                continue
            sfx_duration = min(
                (plano.fin_real_seg or plano.inicio_real_seg + 4) - plano.inicio_real_seg + 1.0,
                12.0,
            )
            src = self._sfx_source(kind, sfx_duration, cache_dir, assets_dir)
            delay_ms = int(plano.inicio_real_seg * 1000)
            inputs += ["-i", str(src)]
            filters.append(
                f"[{idx}:a]volume=0.30,afade=t=in:d=0.4,adelay={delay_ms}|{delay_ms},"
                f"apad=whole_dur={duration:.2f}[s{idx}]"
            )
            labels.append(f"[s{idx}]")
            idx += 1

        whoosh = self._whoosh_source(cache_dir)
        for t in transition_times or []:
            delay_ms = max(0, int((t - 0.15) * 1000))
            inputs += ["-i", str(whoosh)]
            filters.append(
                f"[{idx}:a]volume=0.18,adelay={delay_ms}|{delay_ms},"
                f"apad=whole_dur={duration:.2f}[w{idx}]"
            )
            labels.append(f"[w{idx}]")
            idx += 1

        mix = "".join(labels) + f"amix=inputs={len(labels)}:normalize=0[out]"
        self._run(
            [
                *inputs,
                "-filter_complex", ";".join([*filters, mix]),
                "-map", "[out]",
                "-t", f"{duration:.2f}",
                str(dest),
            ]
        )
        return dest
