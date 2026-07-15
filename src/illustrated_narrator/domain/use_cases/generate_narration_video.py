"""Orquestador de punta a punta: guion + audio real -> video final.

Cada etapa revisa el estado guardado antes de trabajar (resumibilidad).
Transcripción e imágenes son las etapas caras — se saltan si ya están hechas
(la transcripción se persiste en transcript.json porque el karaoke la necesita
en cada corrida); clips y ensamblado siempre se re-corren: son baratos y su
resultado depende de los vecinos (duraciones) y del acabado que más se itera.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path

from illustrated_narrator.domain.entities.plano import Plano, PlanoEstado
from illustrated_narrator.domain.entities.project import NarrationProject
from illustrated_narrator.domain.services.forced_aligner import AlignmentResult, AlignScriptToAudio
from illustrated_narrator.domain.services.pan_direction import pan_direction_for
from illustrated_narrator.domain.services.plano_state import load_planos_state, save_planos_state
from illustrated_narrator.domain.services.motion_profile import resolve_motion
from illustrated_narrator.domain.services.render_timeline import compute_render_durations
from illustrated_narrator.domain.services.retention_plan import (
    motion_floor_for_progress,
    plan_shots,
    progress_map,
)
from illustrated_narrator.domain.services.script_loader import load_guion
from illustrated_narrator.domain.services.shot_assets import ShotAsset, is_video_file, resolve_shot_asset
from illustrated_narrator.domain.services.transcript_store import load_transcript, save_transcript
from illustrated_narrator.domain.use_cases.generate_plano_images import GeneratePlanoImages
from illustrated_narrator.domain.use_cases.research_audio_assets import ResearchAudioAssets
from illustrated_narrator.domain.use_cases.research_plano_media import ResearchPlanoMedia
from illustrated_narrator.adapters.video.ass_writer import write_ass
from illustrated_narrator.ports.transcription import TranscriptionPort
from illustrated_narrator.ports.video_assembler import VideoAssemblerPort

logger = logging.getLogger(__name__)


def _clean_shot(img: Path, images_dir: Path) -> Path:
    """Devuelve una versión sin marcos de la imagen (cacheada en images/clean/)."""
    try:
        from illustrated_narrator.adapters.video.image_cleaner import clean_image

        dest = images_dir / "clean" / img.name
        return clean_image(img, dest)
    except Exception as exc:  # noqa: BLE001 — sin limpieza, se usa la original
        logger.warning("Limpieza de %s falló (%s); uso original", img.name, exc)
        return img


@dataclass
class GenerateVideoReport:
    alignment: AlignmentResult | None = None
    images_generated: int = 0
    images_failed: list[tuple[Plano, str]] = field(default_factory=list)
    clips_rendered: int = 0
    final_video_path: Path | None = None
    media_shots_resolved: int = 0


class GenerateNarrationVideo:
    def __init__(
        self,
        transcriber: TranscriptionPort,
        generate_images: GeneratePlanoImages,
        assembler: VideoAssemblerPort,
        xfade_duration: float = 0.28,
        audio_bed_builder=None,
        canvas: tuple[int, int] = (1920, 1080),
        cta_text: str | None = None,
        cta_duration: float = 3.0,
        research_plano_media: ResearchPlanoMedia | None = None,
        research_audio_assets: ResearchAudioAssets | None = None,
        brand_name: str | None = None,
        brand_intro_duration: float = 2.0,
        accent_color_ass: str | None = None,
        logo_path: Path | None = None,
    ) -> None:
        self._transcriber = transcriber
        self._generate_images = generate_images
        self._assembler = assembler
        self._xfade_duration = xfade_duration
        self._bed_builder = audio_bed_builder
        self._canvas = canvas
        self._cta_text = cta_text or None
        self._cta_duration = cta_duration
        self._research_plano_media = research_plano_media
        self._research_audio_assets = research_audio_assets
        self._brand_name = brand_name or None
        self._brand_intro_duration = brand_intro_duration
        self._accent_color_ass = accent_color_ass
        self._logo_path = logo_path

    def execute(self, project: NarrationProject) -> GenerateVideoReport:
        report = GenerateVideoReport()
        if not project.audio_path.exists():
            raise FileNotFoundError(
                f"Falta {project.audio_path} — graba tu narración completa en una sola toma "
                "y guárdala ahí antes de generar el video."
            )

        guion = load_guion(project.script_path)
        load_planos_state(guion.planos, project.planos_alineados_path)

        transcript = load_transcript(project.transcript_path)
        already_aligned = all(p.inicio_real_seg is not None for p in guion.planos)
        if not already_aligned or transcript is None:
            transcript = self._transcriber.transcribe(
                project.audio_path, language=guion.meta.idioma[:2]
            )
            save_transcript(transcript, project.transcript_path)
        if not already_aligned:
            result = AlignScriptToAudio().execute(guion, transcript)
            report.alignment = result
            if result.unaligned_planos:
                logger.warning(
                    "No se pudieron alinear %d plano(s): %s",
                    len(result.unaligned_planos), ", ".join(result.unaligned_planos),
                )
            save_planos_state(guion.planos, project.planos_alineados_path)

        alignable = [p for p in guion.planos if p.inicio_real_seg is not None]
        alignable.sort(key=lambda p: p.inicio_real_seg)

        # Duraciones de render y plan de tomas ANTES de generar imágenes: un
        # plano largo se parte en varias tomas para no dejar una imagen fija
        # demasiado tiempo (estándar de retención de la herramienta).
        render_durations = compute_render_durations(alignable, self._xfade_duration)
        progress_by_plano = progress_map(alignable, render_durations)
        shots_by_plano = {
            p.id: plan_shots(p, render_durations[p.id], progress=progress_by_plano[p.id])
            for p in alignable
        }

        # Enriquecimiento con medios reales: para cualquier plano (no solo
        # histórico/documental), busca fotos reales antes de generar con IA.
        # Escribe directo en images_dir -- generate_plano_images se salta los
        # shots que ya tienen archivo, así que esto es un fallback silencioso
        # sin tocar ese caso de uso.
        if self._research_plano_media is not None:
            try:
                media_report = self._research_plano_media.execute(
                    alignable,
                    project.images_dir,
                    project.media_dir,
                    project.media_manifest_path,
                    shots_by_plano,
                )
                report.media_shots_resolved = media_report.shots_resolved
            except Exception as exc:  # noqa: BLE001 — sin medios reales, sigue la generación IA
                logger.error("Investigación de medios falló (%s); se genera todo con IA", exc)

        pending_images = [p for p in alignable if p.estado == PlanoEstado.PENDIENTE or not p.imagen_path]
        if pending_images:
            images_report = self._generate_images.execute(
                pending_images, project.images_dir, shots_by_plano, media_dir=project.media_dir
            )
            report.images_generated = len(images_report.generated)
            report.images_failed = images_report.failed
            save_planos_state(guion.planos, project.planos_alineados_path)

        renderable = [p for p in alignable if p.imagen_path and Path(p.imagen_path).exists()]
        clip_paths: list[Path] = []
        for plano in renderable:
            dest = project.clips_dir / f"{plano.id}.mp4"
            # Assets (imagen o video real) de las tomas del plano que existan en disco
            shot_assets = [
                resolve_shot_asset(project.images_dir, project.media_dir, s)
                for s in shots_by_plano[plano.id]
            ]
            fallback_path = Path(plano.imagen_path)
            shot_assets = [a for a in shot_assets if a is not None] or [
                ShotAsset(fallback_path, "video" if is_video_file(fallback_path) else "image")
            ]
            # Limpieza: recorta marcos/bordes uniformes (escaneos con margen
            # blanco, texto de libro) que arruinan el plano y confunden al
            # parallax. Solo aplica a imágenes -- un video real ya viene limpio.
            shot_assets = [
                a if a.media_type == "video" else ShotAsset(_clean_shot(a.path, project.images_dir), "image")
                for a in shot_assets
            ]
            # Siempre re-renderizar: la duración depende de los vecinos y los
            # overlays/acabado se iteran; el encode por HW es barato
            self._assembler.render_plano_clip(
                shot_assets,
                render_durations[plano.id],
                pan_direction_for(plano.id),
                dest,
                overlay=plano.visual.overlay,
                motion=resolve_motion(
                    plano, min_level=motion_floor_for_progress(progress_by_plano[plano.id])
                ),
            )
            plano.clip_path = str(dest)
            plano.estado = PlanoEstado.CLIP_LISTO
            report.clips_rendered += 1
            clip_paths.append(dest)
        save_planos_state(guion.planos, project.planos_alineados_path)

        if not clip_paths:
            raise RuntimeError("Sin clips para ensamblar — revisa la alineación y la generación de imágenes.")

        narration_end = max((p.fin_real_seg or 0) for p in renderable) + 1.2

        from illustrated_narrator.adapters.video.ffmpeg_assembler import chained_duration

        # Tarjeta de apertura con el nombre de marca: antepone un clip fijo
        # y retrasa todo lo demás (narración, captions, CTA, cortes de la
        # cama de audio) exactamente lo que ese clip aporta al timeline final
        # (duración menos el solape del corte hacia el primer plano real).
        intro_offset = 0.0
        if self._brand_name:
            intro = project.clips_dir / "aaa_intro.mp4"
            self._assembler.render_intro_card(
                self._brand_name, self._brand_intro_duration, intro, logo_path=self._logo_path
            )
            first_content_duration = render_durations[renderable[0].id]
            intro_offset = (
                chained_duration(
                    [self._brand_intro_duration, first_content_duration], self._xfade_duration
                )
                - first_content_duration
            )
            clip_paths.insert(0, intro)

        # Tarjeta de cierre (CTA): retiene ofreciendo el siguiente paso.
        # El inicio en la línea de tiempo se deriva de las duraciones ya
        # conocidas (cada xfade solapa xfade_duration), sin sondear archivos.
        cta_start = None
        if self._cta_text:
            end_card = project.clips_dir / "zzz_end_card.mp4"
            self._assembler.render_end_card(self._cta_text, self._cta_duration, end_card)
            # Inicio de la tarjeta = duración del contenido encadenado (misma
            # función que usa el ensamblador, así el CTA cae justo en el corte)
            plano_durations = [render_durations[p.id] for p in renderable]
            if self._brand_name:
                plano_durations = [self._brand_intro_duration, *plano_durations]
            cta_start = chained_duration(plano_durations, self._xfade_duration)
            clip_paths.append(end_card)

        write_ass(
            renderable,
            project.captions_path,
            transcript=transcript,
            meta=guion.meta,
            play_res=self._canvas,
            cta_text=self._cta_text,
            cta_start_seconds=cta_start,
            cta_duration=self._cta_duration,
            accent_color_ass=self._accent_color_ass,
            time_offset_seconds=intro_offset,
        )

        if self._research_audio_assets is not None:
            try:
                self._research_audio_assets.execute(guion, project.assets_dir)
            except Exception as exc:  # noqa: BLE001 — sin audio real, sigue el generador procedural
                logger.error("Investigación de audio falló (%s); se usa la cama procedural", exc)

        bed_path = None
        if self._bed_builder is not None:
            total = intro_offset + narration_end + (self._cta_duration if self._cta_text else 0)
            # La cama de música/SFX NO se retrasa (suena limpia desde t=0 bajo
            # la intro); solo se desplazan los MOMENTOS de corte para que
            # sigan cayendo justo donde el video ya alargado los tiene.
            transition_times = ([intro_offset] if intro_offset else []) + [
                intro_offset + float(p.inicio_real_seg) for p in renderable[1:]
            ]
            try:
                bed_path = self._bed_builder.build(
                    renderable,
                    duration=total,
                    assets_dir=project.assets_dir,
                    cache_dir=project.assets_dir / "auto",
                    transition_times=transition_times,
                )
            except Exception as exc:  # noqa: BLE001 — sin cama de audio no se cae el video
                logger.error("Cama de audio falló (%s); el video sale solo con narración", exc)

        self._assembler.assemble(
            clip_paths, project.captions_path, project.audio_path,
            project.final_video_path, xfade_duration=self._xfade_duration,
            bed_path=bed_path, audio_delay_seconds=intro_offset,
        )
        report.final_video_path = project.final_video_path
        return report
