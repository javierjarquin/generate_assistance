"""Cliente HTTP de AUTOMATIC1111 WebUI + extensión sd-webui-animatediff
(motion module estándar, NO AnimateLCM), corriendo local -- mismo servidor
que Automatic1111ImageAdapter, no lo autolanza (ver ese adaptador).

Último recurso cuando NINGUNA fuente real (búsqueda + país + continente)
encontró nada para un plano: genera un clip corto en vez de dejarlo sin
medio.

Por qué el módulo estándar y NO AnimateLCM (aunque sea ~2.5x más lento):
confirmado con pruebas reales (GPU del proyecto, AMD RX 5500 XT, DirectML,
Windows recién reiniciado) que AnimateLCM (8 pasos, CFG 1.5) colapsa en
ruido/patrones repetidos para contenido de bajo detalle -- fondos casi
sólidos, logos minimalistas -- que es EXACTAMENTE el tipo de plano que más
necesita este fallback (los planos con contenido rico casi siempre
encuentran medio real en la búsqueda). El módulo estándar (20 pasos, CFG
7, sampler normal) dio salida coherente en 5/5 pruebas reales, tanto para
contenido rico como minimalista -- AnimateLCM falló las 3/3 pruebas con
contenido minimalista pese a devolver 200 OK (salida inválida silenciosa,
no un error). Con menos tolerancia a fallos silenciosos, más lento pero
confiable gana.
"""

import base64
import logging
from pathlib import Path

import requests

from illustrated_narrator.ports.video_generator import VideoGenerationRequest, VideoGeneratorPort

logger = logging.getLogger(__name__)

_HEALTH_TIMEOUT = 5
# Medido en pruebas reales: ~9m40s para 16 frames (2s) con el módulo
# estándar. Margen amplio para variación de hardware/carga del sistema.
_GENERATE_TIMEOUT = 1800

_MOTION_MODULE = "mm_sd15_v2.safetensors"
_STEPS = 20
_CFG_SCALE = 7
_SAMPLER = "Euler a"


class AnimateDiffA1111Adapter(VideoGeneratorPort):
    def __init__(self, base_url: str, session: requests.Session | None = None) -> None:
        self._base_url = base_url.rstrip("/")
        self._http = session or requests.Session()

    def is_available(self) -> bool:
        try:
            resp = self._http.get(f"{self._base_url}/sdapi/v1/options", timeout=_HEALTH_TIMEOUT)
            return resp.ok
        except requests.RequestException:
            return False

    def generate(self, request: VideoGenerationRequest, dest: Path) -> Path:
        frames = max(8, round(request.duration_seconds * request.fps))
        payload = {
            "prompt": request.prompt,
            "negative_prompt": request.negative_prompt,
            "steps": _STEPS,
            "width": request.width,
            "height": request.height,
            "cfg_scale": _CFG_SCALE,
            "sampler_name": _SAMPLER,
            "alwayson_scripts": {
                "AnimateDiff": {
                    "args": [{
                        "model": _MOTION_MODULE,
                        "enable": True,
                        "video_length": frames,
                        "fps": request.fps,
                        "loop_number": 0,
                        "closed_loop": "R-P",
                        "batch_size": frames,
                        "stride": 1,
                        "overlap": -1,
                        "format": ["MP4"],
                    }]
                }
            },
        }
        resp = self._http.post(
            f"{self._base_url}/sdapi/v1/txt2img", json=payload, timeout=_GENERATE_TIMEOUT
        )
        resp.raise_for_status()
        images = resp.json().get("images") or []
        mp4_bytes = next((b for b in (self._as_mp4(im) for im in images) if b is not None), None)
        if mp4_bytes is None:
            raise RuntimeError(
                f"AnimateDiff no devolvió un MP4 para el prompt: {request.prompt[:80]}"
            )

        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(mp4_bytes)
        return dest

    @staticmethod
    def _as_mp4(image_b64: str) -> bytes | None:
        raw = base64.b64decode(image_b64)
        return raw if raw[4:8] == b"ftyp" else None
