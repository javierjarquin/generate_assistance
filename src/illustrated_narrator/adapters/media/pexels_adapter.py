"""Cliente de la API de Pexels (fotos de stock reales).

Key gratuita en pexels.com/api. Licencia Pexels: uso libre comercial/personal,
atribución no obligatoria (se guarda igual en el manifest por cortesía).
"""

import logging
from pathlib import Path

import requests

from illustrated_narrator.ports.stock_media import MediaCandidate, StockImagePort

logger = logging.getLogger(__name__)

_TIMEOUT = 15


class PexelsImageAdapter(StockImagePort):
    def __init__(self, api_key: str | None, session: requests.Session | None = None) -> None:
        self._api_key = api_key or ""
        self._http = session or requests.Session()

    def is_available(self) -> bool:
        return bool(self._api_key)

    def search(self, query: str, dest_dir: Path, count: int) -> list[MediaCandidate]:
        if not self._api_key or not query.strip():
            return []
        try:
            resp = self._http.get(
                "https://api.pexels.com/v1/search",
                headers={"Authorization": self._api_key},
                params={"query": query, "per_page": count, "orientation": "landscape"},
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
            photos = resp.json().get("photos", [])
        except (requests.RequestException, ValueError) as exc:
            logger.warning("Pexels: búsqueda '%s' falló (%s)", query, exc)
            return []

        dest_dir.mkdir(parents=True, exist_ok=True)
        candidates: list[MediaCandidate] = []
        for photo in photos:
            src = photo.get("src", {})
            image_url = src.get("large2x") or src.get("large") or src.get("original")
            if not image_url:
                continue
            dest = dest_dir / f"pexels_{photo['id']}.jpg"
            try:
                img_resp = self._http.get(image_url, timeout=_TIMEOUT)
                img_resp.raise_for_status()
                dest.write_bytes(img_resp.content)
            except requests.RequestException as exc:
                logger.warning("Pexels: descarga de %s falló (%s)", image_url, exc)
                continue
            candidates.append(
                MediaCandidate(
                    path=dest,
                    title=photo.get("alt") or query,
                    source="pexels",
                    source_url=photo.get("url", image_url),
                    license="Pexels License (uso libre, atribución no requerida)",
                    author=photo.get("photographer"),
                )
            )
        return candidates
