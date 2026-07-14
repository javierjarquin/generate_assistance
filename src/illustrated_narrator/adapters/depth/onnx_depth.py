"""Estimación de profundidad con Depth-Anything V2 (small) vía onnxruntime en CPU.

El modelo corre en CPU en pocos segundos por imagen. Si el modelo o las deps
faltan, `is_available()` devuelve False y el pipeline cae a Ken Burns sin
parallax (degradación limpia, no se cae).
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_INPUT_SIZE = 518  # múltiplo de 14 que pide Depth-Anything
_MEAN = (0.485, 0.456, 0.406)
_STD = (0.229, 0.224, 0.225)


class OnnxDepthEstimator:
    def __init__(self, model_path: Path) -> None:
        self._model_path = Path(model_path)
        self._session = None

    def is_available(self) -> bool:
        if not self._model_path.exists():
            return False
        try:
            import onnxruntime  # noqa: F401
            import cv2  # noqa: F401
            import numpy  # noqa: F401
        except ImportError:
            return False
        return True

    def _load(self):
        if self._session is None:
            import onnxruntime as ort

            self._session = ort.InferenceSession(
                str(self._model_path), providers=["CPUExecutionProvider"]
            )
        return self._session

    def estimate(self, image_path: Path):
        import cv2
        import numpy as np

        session = self._load()
        bgr = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
        if bgr is None:
            raise RuntimeError(f"No se pudo leer la imagen {image_path}")
        h0, w0 = bgr.shape[:2]

        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        resized = cv2.resize(rgb, (_INPUT_SIZE, _INPUT_SIZE), interpolation=cv2.INTER_CUBIC)
        norm = (resized - np.array(_MEAN, np.float32)) / np.array(_STD, np.float32)
        tensor = np.transpose(norm, (2, 0, 1))[None, ...].astype(np.float32)

        name = session.get_inputs()[0].name
        depth = session.run(None, {name: tensor})[0][0]  # HxW

        # Depth-Anything: valor mayor = más cerca. Normalizar a 0..1 y llevar al
        # tamaño original.
        depth = cv2.resize(depth, (w0, h0), interpolation=cv2.INTER_CUBIC)
        d_min, d_max = float(depth.min()), float(depth.max())
        if d_max - d_min < 1e-6:
            return np.full((h0, w0), 0.5, np.float32)
        near = (depth - d_min) / (d_max - d_min)
        logger.info("Profundidad estimada para %s (%dx%d)", image_path.name, w0, h0)
        return near.astype(np.float32)


class RadialDepthEstimator:
    """Fallback sin modelo: profundidad radial (centro cerca, bordes lejos).

    No es real pero da algo de parallax verosímil (el centro "flota" sobre el
    fondo) cuando no hay modelo de profundidad instalado."""

    def is_available(self) -> bool:
        try:
            import numpy  # noqa: F401
        except ImportError:
            return False
        return True

    def estimate(self, image_path: Path):
        import cv2
        import numpy as np

        bgr = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
        h, w = bgr.shape[:2]
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        cx, cy = w / 2, h / 2
        r = np.sqrt(((xx - cx) / cx) ** 2 + ((yy - cy) / cy) ** 2)
        near = 1.0 - np.clip(r / np.sqrt(2), 0, 1)
        return near.astype(np.float32)
