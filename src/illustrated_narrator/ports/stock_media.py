from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class MediaCandidate:
    """Un resultado real (no generado) encontrado por una fuente de stock."""

    path: Path
    title: str
    source: str  # "pexels" | "wikimedia"
    source_url: str
    license: str
    author: str | None = None


class StockImagePort(ABC):
    @abstractmethod
    def is_available(self) -> bool: ...

    @abstractmethod
    def search(self, query: str, dest_dir: Path, count: int) -> list[MediaCandidate]:
        """Busca y descarga hasta `count` candidatos a `dest_dir`. Lista vacía
        si no hay resultados — nunca lanza por "sin resultados", solo por
        fallos de red/API que el llamador decide cómo tratar."""
