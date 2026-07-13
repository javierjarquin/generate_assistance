"""Genera la imagen IA de cada plano a partir de su prompt_ia + un sufijo de
estilo fijo (para que todas las imagenes del video se vean consistentes).
"""

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

from illustrated_narrator.domain.entities.plano import Plano, PlanoEstado
from illustrated_narrator.ports.image_generator import ImageGenerationRequest, ImageGeneratorPort


@dataclass
class GenerateImagesReport:
    generated: list[Plano] = field(default_factory=list)
    failed: list[tuple[Plano, str]] = field(default_factory=list)


def _seed_for(plano_id: str) -> int:
    """Semilla determinista por plano: reproducible entre corridas, a diferencia de hash()."""
    digest = hashlib.sha256(plano_id.encode("utf-8")).digest()
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
    ) -> None:
        self._images = image_generator
        self._style_suffix = style_suffix
        self._negative_prompt = negative_prompt
        self._steps = steps
        self._cfg_scale = cfg_scale
        self._sampler = sampler_name

    def execute(self, planos: list[Plano], images_dir: Path) -> GenerateImagesReport:
        report = GenerateImagesReport()
        if not self._images.is_available():
            raise RuntimeError(
                "El servicio de generación de imágenes (A1111) no responde. "
                "Arráncalo con webui-user.bat --api y vuelve a intentar."
            )
        for plano in planos:
            try:
                prompt = f"{plano.visual.prompt_ia}, {self._style_suffix}"
                request = ImageGenerationRequest(
                    prompt=prompt,
                    negative_prompt=self._negative_prompt,
                    steps=self._steps,
                    cfg_scale=self._cfg_scale,
                    sampler_name=self._sampler,
                    seed=_seed_for(plano.id),
                )
                dest = images_dir / f"{plano.id}.png"
                self._images.generate(request, dest)
                plano.imagen_path = str(dest)
                plano.estado = PlanoEstado.IMAGEN_GENERADA
                report.generated.append(plano)
            except Exception as exc:  # noqa: BLE001 — un plano fallido no frena el resto
                plano.estado = PlanoEstado.FALLIDO
                report.failed.append((plano, str(exc)))
        return report
