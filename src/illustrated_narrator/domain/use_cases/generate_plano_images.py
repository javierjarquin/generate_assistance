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
"""

import hashlib
import logging
from dataclasses import dataclass, field
from pathlib import Path

from illustrated_narrator.domain.entities.plano import Plano, PlanoEstado
from illustrated_narrator.domain.services.retention_plan import Shot, variation_suffix
from illustrated_narrator.domain.services.shot_assets import shot_image_path, shot_video_path
from illustrated_narrator.ports.image_generator import ImageGenerationRequest, ImageGeneratorPort

logger = logging.getLogger(__name__)

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
    ) -> None:
        self._images = image_generator
        self._style_suffix = style_suffix
        self._negative_prompt = negative_prompt
        self._steps = steps
        self._cfg_scale = cfg_scale
        self._sampler = sampler_name
        self._width = width
        self._height = height

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
