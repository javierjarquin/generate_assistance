"""Genera las imágenes IA de cada plano a partir de su prompt_ia + un sufijo de
estilo fijo (consistencia visual entre todas las imágenes del video).

Multi-toma: un plano largo puede necesitar varias imágenes para que ninguna
quede fija más de unos segundos (ver retention_plan). La primera toma usa el
prompt tal cual; las extra añaden una variación de encuadre y una semilla
distinta — mismo tema, distinto ángulo.

Si a UNA toma le falta medio (típico con NARR_IMAGE_BACKEND=none: no hay
IA de respaldo), no se tira el plano entero -- se saltea esa toma sola y
las demás tomas ya resueltas del mismo plano se reparten su duración
(render_plano_clip ya divide `duration_seconds` entre las tomas válidas
que recibe, así que una toma de menos simplemente se cubre estirando las
otras). El plano solo se marca FALLIDO si ninguna de sus tomas tiene medio
real -- ahí sí no hay nada que estirar.

Último recurso, opt-in (`video_generator` + `max_video_fallback_planos` >
0): si un plano se queda sin NINGUNA toma resuelta después de agotar
búsqueda real + país + continente (ver ResearchPlanoMedia), y es un tipo
conceptual/atmosférico (imagen_ia o grafico_movimiento -- NUNCA
archivo_historico, que afirma ser documental real), genera un clip corto
de video con IA en vez de fallar. Un solo clip por plano alcanza:
_render_video_shot ya hace loop si el video es más corto que la toma, así
que no hace falta generar tanto como dure el plano real. Acotado a un
puñado de planos por corrida (max_video_fallback_planos) para no volar el
tiempo total -- medido en una GPU real: ~4-9 min por clip."""

import hashlib
import logging
from dataclasses import dataclass, field
from pathlib import Path

from illustrated_narrator.domain.entities.plano import Plano, PlanoEstado, VisualTipo
from illustrated_narrator.domain.services.retention_plan import Shot, variation_suffix
from illustrated_narrator.domain.services.shot_assets import shot_image_path, shot_video_path
from illustrated_narrator.ports.image_generator import ImageGenerationRequest, ImageGeneratorPort
from illustrated_narrator.ports.video_generator import VideoGenerationRequest, VideoGeneratorPort

logger = logging.getLogger(__name__)

# Tipos de plano elegibles para el fallback de video-IA: conceptuales/
# atmosféricos, nunca los que afirman ser documento/archivo real.
_VIDEO_FALLBACK_TIPOS = (VisualTipo.IMAGEN_IA, VisualTipo.GRAFICO_MOVIMIENTO)
# Resolución validada en la prueba real (AMD RX 5500 XT, DirectML) -- más
# alta sube el riesgo de VRAM/tiempo sin haberlo probado.
_VIDEO_WIDTH = 512
_VIDEO_HEIGHT = 512

__all__ = ["GenerateImagesReport", "GeneratePlanoImages", "shot_image_path"]


@dataclass
class GenerateImagesReport:
    generated: list[Plano] = field(default_factory=list)
    failed: list[tuple[Plano, str]] = field(default_factory=list)
    shots_generated: int = 0


def _seed_for(shot_id: str) -> int:
    """Semilla determinista por toma: reproducible entre corridas."""
    digest = hashlib.sha256(shot_id.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") % (2**31)


class GeneratePlanoImages:
    def __init__(
        self,
        image_generator: ImageGeneratorPort,
        style_suffix: str,
        negative_prompt: str,
        steps: int,
        cfg_scale: float,
        sampler_name: str,
        width: int = 768,
        height: int = 448,
        video_generator: VideoGeneratorPort | None = None,
        max_video_fallback_planos: int = 0,
        max_video_fallback_seconds: float = 2.0,
    ) -> None:
        self._images = image_generator
        self._style_suffix = style_suffix
        self._negative_prompt = negative_prompt
        self._steps = steps
        self._cfg_scale = cfg_scale
        self._sampler = sampler_name
        self._width = width
        self._height = height
        self._video_generator = video_generator
        self._max_video_fallback_planos = max_video_fallback_planos
        self._max_video_fallback_seconds = max_video_fallback_seconds

    def execute(
        self,
        planos: list[Plano],
        images_dir: Path,
        shots_by_plano: dict[str, list[Shot]] | None = None,
        media_dir: Path | None = None,
    ) -> GenerateImagesReport:
        report = GenerateImagesReport()
        if not self._images.is_available():
            raise RuntimeError(
                "El servicio de generación de imágenes (A1111) no responde. "
                "Arráncalo con tools\\run_a1111.bat y vuelve a intentar."
            )
        video_fallback_used = 0
        for plano in planos:
            shots = (shots_by_plano or {}).get(plano.id) or [
                Shot(plano_id=plano.id, index=0, total=1)
            ]
            first_resolved: Path | None = None
            last_error: str | None = None
            for shot in shots:
                try:
                    resolved = self._resolve_or_generate_shot(
                        plano, shot, images_dir, media_dir, report
                    )
                except Exception as exc:  # noqa: BLE001 — una toma sin medio no tira el plano si otras sí resolvieron
                    last_error = str(exc)
                    logger.warning(
                        "%s sin medio real (%s); las demás tomas del plano cubren su duración",
                        shot.shot_id, exc,
                    )
                    continue
                if not shot.is_extra:
                    plano.imagen_path = str(resolved)
                first_resolved = first_resolved or resolved

            if first_resolved is None and self._video_fallback_eligible(
                plano, video_fallback_used
            ):
                try:
                    first_resolved = self._generate_video_fallback(plano, shots, media_dir)
                    video_fallback_used += 1
                    logger.warning(
                        "%s sin medio real en ninguna fuente; generado con video-IA "
                        "(fallback %d/%d de esta corrida)",
                        plano.id, video_fallback_used, self._max_video_fallback_planos,
                    )
                except Exception as exc:  # noqa: BLE001 — último recurso: si también falla, el plano queda FALLIDO como siempre
                    last_error = str(exc)
                    logger.warning("Video-IA de respaldo falló para %s (%s)", plano.id, exc)

            if first_resolved is not None:
                if not plano.imagen_path:
                    # La toma "principal" (index 0) fue justo la que faltó, pero
                    # otra toma del mismo plano sí resolvió -- se usa esa como
                    # imagen del plano para que no lo descarte `renderable` más
                    # abajo (el render por-toma igual usa la lista completa).
                    plano.imagen_path = str(first_resolved)
                plano.estado = PlanoEstado.IMAGEN_GENERADA
                report.generated.append(plano)
            else:
                plano.estado = PlanoEstado.FALLIDO
                report.failed.append((plano, last_error or "sin medio real para ninguna toma de este plano"))
        return report

    def _resolve_or_generate_shot(
        self, plano: Plano, shot: Shot, images_dir: Path, media_dir: Path | None,
        report: GenerateImagesReport,
    ) -> Path:
        if media_dir is not None:
            video = shot_video_path(media_dir, shot)
            if video.exists():  # B-roll real ya resuelto: no generar con IA
                return video
        dest = shot_image_path(images_dir, shot)
        if dest.exists():  # resumible: no re-generar tomas ya hechas
            return dest
        prompt = f"{plano.visual.prompt_ia}{variation_suffix(shot)}, {self._style_suffix}"
        request = ImageGenerationRequest(
            prompt=prompt,
            label=plano.visual.descripcion or plano.narracion,
            negative_prompt=self._negative_prompt,
            width=self._width,
            height=self._height,
            steps=self._steps,
            cfg_scale=self._cfg_scale,
            sampler_name=self._sampler,
            seed=_seed_for(shot.shot_id),
        )
        self._images.generate(request, dest)
        report.shots_generated += 1
        return dest

    def _video_fallback_eligible(self, plano: Plano, video_fallback_used: int) -> bool:
        return (
            self._video_generator is not None
            and video_fallback_used < self._max_video_fallback_planos
            and plano.visual.tipo in _VIDEO_FALLBACK_TIPOS
            and self._video_generator.is_available()
        )

    def _generate_video_fallback(
        self, plano: Plano, shots: list[Shot], media_dir: Path | None
    ) -> Path:
        if media_dir is None:
            raise RuntimeError("sin media_dir, no se puede escribir el video generado")
        # Un solo clip para TODO el plano (no por toma): _render_video_shot
        # ya hace loop si el clip es más corto que la toma, así que basta
        # con escribirlo en la ruta de la primera toma.
        dest = shot_video_path(media_dir, shots[0])
        # SIN style_suffix: confirmado en una prueba real (misma GPU) que un
        # prompt largo (prompt_ia + el sufijo de estilo que sí usan las
        # imágenes fijas) se queda sin VRAM incluso aislado -- el batch
        # temporal de AnimateDiff ya está al límite en esta tarjeta con un
        # prompt corto solo. No reagregar sin volver a probar.
        request = VideoGenerationRequest(
            prompt=plano.visual.prompt_ia,
            negative_prompt=self._negative_prompt,
            width=_VIDEO_WIDTH,
            height=_VIDEO_HEIGHT,
            duration_seconds=self._max_video_fallback_seconds,
        )
        self._video_generator.generate(request, dest)
        return dest
