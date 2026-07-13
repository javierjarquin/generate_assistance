"""Cliente HTTP de AUTOMATIC1111 WebUI (--api), corriendo local.

Requiere que A1111 ya esté arrancado por separado (webui-user.bat --api) --
este adaptador no lo autolanza (ver plan: fragilidad de ruta/tiempo de carga
variable no vale la pena para una herramienta de un solo usuario).
"""

import base64
import logging
from pathlib import Path

import requests

from illustrated_narrator.ports.image_generator import ImageGenerationRequest, ImageGeneratorPort

logger = logging.getLogger(__name__)

_HEALTH_TIMEOUT = 5
# fp32 en GPU modesta (T600) tarda 3-5 min por imagen: margen amplio
_GENERATE_TIMEOUT = 900


class Automatic1111ImageAdapter(ImageGeneratorPort):
    def __init__(
        self,
        base_url: str,
        checkpoint: str | None = None,
        session: requests.Session | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        # Nombre del checkpoint a forzar por generación (override_settings). Si es
        # None se usa el que A1111 tenga cargado — el checkpoint base SD 1.5 obedece
        # mal los prompts; un modelo afinado (DreamShaper, Realistic Vision) mejora
        # calidad y fidelidad sin tocar el pipeline.
        self._checkpoint = checkpoint or None
        self._http = session or requests.Session()

    def is_available(self) -> bool:
        try:
            resp = self._http.get(f"{self._base_url}/sdapi/v1/options", timeout=_HEALTH_TIMEOUT)
            return resp.ok
        except requests.RequestException:
            return False

    def generate(self, request: ImageGenerationRequest, dest: Path) -> Path:
        payload = {
            "prompt": request.prompt,
            "negative_prompt": request.negative_prompt,
            "width": request.width,
            "height": request.height,
            "steps": request.steps,
            "cfg_scale": request.cfg_scale,
            "sampler_name": request.sampler_name,
            "seed": request.seed,
        }
        if self._checkpoint:
            payload["override_settings"] = {"sd_model_checkpoint": self._checkpoint}
            payload["override_settings_restore_afterwards"] = False
        resp = self._http.post(
            f"{self._base_url}/sdapi/v1/txt2img", json=payload, timeout=_GENERATE_TIMEOUT
        )
        resp.raise_for_status()
        images = resp.json().get("images")
        if not images:
            raise RuntimeError(f"A1111 no devolvió imágenes para el prompt: {request.prompt[:80]}")

        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(base64.b64decode(images[0]))
        return dest
