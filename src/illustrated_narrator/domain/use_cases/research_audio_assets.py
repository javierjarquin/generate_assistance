"""Investiga música ambiental y SFX reales (Freesound) para reemplazar los
generadores procedurales de audio_bed.py — solo si el usuario no dejó ya sus
propios archivos en assets_dir (ese mecanismo de "el archivo real gana" no
cambia, ver adapters/audio/audio_bed.py).
"""

import logging
from pathlib import Path

from illustrated_narrator.domain.entities.guion import Guion
from illustrated_narrator.domain.services.sfx_taxonomy import SFX_KEYWORDS, sfx_kind
from illustrated_narrator.ports.stock_audio import StockAudioPort

logger = logging.getLogger(__name__)

_MUSIC_FILENAMES = ("music.mp3", "music.wav", "musica.mp3", "musica.wav")


class ResearchAudioAssets:
    def __init__(self, source: StockAudioPort | None) -> None:
        self._source = source

    def execute(self, guion: Guion, assets_dir: Path) -> None:
        if self._source is None or not self._source.is_available():
            return
        self._ensure_music(guion, assets_dir)
        self._ensure_sfx(guion, assets_dir)

    def _ensure_music(self, guion: Guion, assets_dir: Path) -> None:
        if any((assets_dir / name).exists() for name in _MUSIC_FILENAMES):
            return
        query = next((p.audio.musica for p in guion.planos if p.audio.musica), None)
        query = query or f"{guion.meta.serie} {guion.meta.titulo} ambient music".strip()
        candidate = self._safe_find(query, assets_dir, "music")
        if candidate is not None:
            candidate.path.rename(assets_dir / f"music{candidate.path.suffix}")

    def _ensure_sfx(self, guion: Guion, assets_dir: Path) -> None:
        kinds_needed = {sfx_kind(p.audio.sfx) for p in guion.planos if p.audio.sfx} - {None}
        if not kinds_needed:
            return
        sfx_dir = assets_dir / "sfx"
        for kind in kinds_needed:
            if any((sfx_dir / f"{kind}.{ext}").exists() for ext in ("wav", "mp3")):
                continue
            query_word = next(k for k, v in SFX_KEYWORDS.items() if v == kind)
            candidate = self._safe_find(query_word, sfx_dir, kind)
            if candidate is not None:
                sfx_dir.mkdir(parents=True, exist_ok=True)
                candidate.path.rename(sfx_dir / f"{kind}{candidate.path.suffix}")

    def _safe_find(self, query: str, dest_dir: Path, kind: str):
        try:
            return self._source.find(query, dest_dir, kind)
        except Exception as exc:  # noqa: BLE001 — sin audio real, sigue el generador procedural
            logger.warning("Investigación de audio falló para '%s' (%s)", query, exc)
            return None
