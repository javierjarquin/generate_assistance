"""Orquestador de punta a punta: guion + audio real -> video final.

Cada etapa revisa el estado guardado en planos_alineados.json antes de
trabajar (ver plan: resumibilidad). Transcripción/alineación e imágenes son
las etapas caras -- se saltan si ya están hechas; el ensamblado final siempre
se re-corre (es barato y es lo que más se itera: subtítulos, transiciones).
"""

import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from illustrated_narrator.domain.entities.plano import Plano, PlanoEstado
from illustrated_narrator.domain.entities.project import NarrationProject
from illustrated_narrator.domain.services.forced_aligner import AlignmentResult, AlignScriptToAudio
from illustrated_narrator.domain.services.pan_direction import pan_direction_for
from illustrated_narrator.domain.services.plano_state import load_planos_state, save_planos_state
from illustrated_narrator.domain.services.script_loader import load_guion
from illustrated_narrator.domain.use_cases.generate_plano_images import GeneratePlanoImages
from illustrated_narrator.adapters.video.ass_writer import write_ass
from illustrated_narrator.ports.transcription import TranscriptionPort
from illustrated_narrator.ports.video_assembler import VideoAssemblerPort

logger = logging.getLogger(__name__)


@dataclass
class GenerateVideoReport:
    alignment: AlignmentResult | None = None
    images_generated: int = 0
    images_failed: list[tuple[Plano, str]] = field(default_factory=list)
    clips_rendered: int = 0
    final_video_path: Path | None = None


class GenerateNarrationVideo:
    def __init__(
        self,
        transcriber: TranscriptionPort,
        generate_images: GeneratePlanoImages,
        assembler: VideoAssemblerPort,
        xfade_duration: float = 0.5,
    ) -> None:
        self._transcriber = transcriber
        self._generate_images = generate_images
        self._assembler = assembler
        self._xfade_duration = xfade_duration

    def execute(self, project: NarrationProject) -> GenerateVideoReport:
        report = GenerateVideoReport()
        if not project.audio_path.exists():
            raise FileNotFoundError(
                f"Falta {project.audio_path} — graba tu narración completa en una sola toma "
                "y guárdala ahí antes de generar el video."
            )

        guion = load_guion(project.script_path)
        load_planos_state(guion.planos, project.planos_alineados_path)

        already_aligned = all(p.inicio_real_seg is not None for p in guion.planos)
        if not already_aligned:
            transcript = self._transcriber.transcribe(project.audio_path, language=guion.meta.idioma[:2])
            result = AlignScriptToAudio().execute(guion, transcript)
            report.alignment = result
            if result.unaligned_planos:
                logger.warning(
                    "No se pudieron alinear %d plano(s): %s",
                    len(result.unaligned_planos), ", ".join(result.unaligned_planos),
                )
            save_planos_state(guion.planos, project.planos_alineados_path)

        alignable = [p for p in guion.planos if p.inicio_real_seg is not None]
        pending_images = [p for p in alignable if p.estado == PlanoEstado.PENDIENTE or not p.imagen_path]
        if pending_images:
            images_report = self._generate_images.execute(pending_images, project.images_dir)
            report.images_generated = len(images_report.generated)
            report.images_failed = images_report.failed
            save_planos_state(guion.planos, project.planos_alineados_path)

        renderable = [p for p in alignable if p.imagen_path and Path(p.imagen_path).exists()]
        clip_paths: list[Path] = []
        for plano in renderable:
            dest = project.clips_dir / f"{plano.id}.mp4"
            if not dest.exists():
                self._assembler.render_plano_clip(
                    Path(plano.imagen_path), plano.duracion_real_seg, pan_direction_for(plano.id), dest
                )
                plano.clip_path = str(dest)
                plano.estado = PlanoEstado.CLIP_LISTO
                report.clips_rendered += 1
            clip_paths.append(dest)
        save_planos_state(guion.planos, project.planos_alineados_path)

        if not clip_paths:
            raise RuntimeError("Sin clips para ensamblar — revisa la alineación y la generación de imágenes.")

        write_ass(renderable, project.captions_path)
        self._assembler.assemble(
            clip_paths, project.captions_path, project.audio_path,
            project.final_video_path, xfade_duration=self._xfade_duration,
        )
        report.final_video_path = project.final_video_path
        return report
