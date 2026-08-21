"""Backend 'sin IA': nunca genera imágenes, exige medio real para cada toma.

Pensado para el lote desatendido (procesar_lote.ps1): garantiza que ninguna
toma sin match de investigación de medios termine generada con Stable
Diffusion ni con un cartel de debug -- si falta un medio real para una toma,
se reporta como fallo explícito del plano (ver GeneratePlanoImages) en vez de
producir un video parcial o con IA de por medio.
"""

from pathlib import Path

from illustrated_narrator.ports.image_generator import ImageGenerationRequest, ImageGeneratorPort


class NullImageGenerator(ImageGeneratorPort):
    def is_available(self) -> bool:
        return True

    def generate(self, request: ImageGenerationRequest, dest: Path) -> Path:
        raise RuntimeError(
            "No se encontró medio real para esta toma y NARR_IMAGE_BACKEND=none "
            "(generación de imágenes IA deshabilitada)."
        )
