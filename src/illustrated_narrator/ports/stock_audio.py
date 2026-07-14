from abc import ABC, abstractmethod
from pathlib import Path

from illustrated_narrator.ports.stock_media import MediaCandidate


class StockAudioPort(ABC):
    @abstractmethod
    def is_available(self) -> bool: ...

    @abstractmethod
    def find(self, query: str, dest_dir: Path, kind: str) -> MediaCandidate | None:
        """Busca y descarga el mejor resultado para `query`/`kind` (p.ej.
        "music" o un kind de SFX). None si no hay resultados usables."""
