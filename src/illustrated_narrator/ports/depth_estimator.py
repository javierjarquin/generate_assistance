"""Puerto de estimación de profundidad: de una imagen a un mapa de profundidad
(near=1, far=0) que alimenta el parallax 2.5D."""

from abc import ABC, abstractmethod
from pathlib import Path


class DepthEstimatorPort(ABC):
    @abstractmethod
    def estimate(self, image_path: Path):
        """Devuelve un ndarray float32 HxW normalizado 0..1 (1 = más cerca)."""

    @abstractmethod
    def is_available(self) -> bool:
        """True si el estimador puede correr (modelo cargado / deps presentes)."""
