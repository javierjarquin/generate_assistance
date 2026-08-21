"""Cliente de la API pública de NASA Images -- sin API key.

Todo el material es obra del gobierno de EE.UU. y por ley es dominio
público (no hay licencia que verificar por archivo, a diferencia de
Wikimedia/Openverse). Fuente de nicho: solo aporta para planos de temática
espacial/aeronáutica -- para el resto de queries normalmente no devuelve
nada relevante y relevance_score lo descarta sin costo extra más allá de
la llamada de red.
"""

import logging
from pathlib import Path

import requests

from illustrated_narrator.ports.stock_media import MediaCandidate, StockImagePort

logger = logging.getLogger(__name__)

_TIMEOUT = 15
_API_URL = "https://images-api.nasa.gov/search"
_USER_AGENT = "illustrated-narrator/1.0 (local tool, single user)"


class NasaImagesAdapter(StockImagePort):
    def __init__(self, session: requests.Session | None = None) -> None:
        self._http = session or requests.Session()

    def is_available(self) -> bool:
        return True  # API pública, sin key

    def search(self, query: str, dest_dir: Path, count: int) -> list[MediaCandidate]:
        if not query.strip():
            return []
        try:
            resp = self._http.get(
                _API_URL,
                params={"q": query, "media_type": "image"},
                headers={"User-Agent": _USER_AGENT},
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
            items = (resp.json().get("collection", {}).get("items") or [])[:count]
        except (requests.RequestException, ValueError) as exc:
            logger.warning("NASA Images: búsqueda '%s' falló (%s)", query, exc)
            return []

        dest_dir.mkdir(parents=True, exist_ok=True)
        candidates: list[MediaCandidate] = []
        for item in items:
            data = (item.get("data") or [{}])[0]
            links = item.get("links") or []
            url = next((link["href"] for link in links if link.get("rel") == "preview"), None)
            if not url:
                continue
            nasa_id = data.get("nasa_id") or str(len(candidates))
            dest = dest_dir / f"nasa_{nasa_id}{Path(url).suffix.lower() or '.jpg'}"
            try:
                img_resp = self._http.get(url, timeout=_TIMEOUT)
                img_resp.raise_for_status()
                dest.write_bytes(img_resp.content)
            except requests.RequestException as exc:
                logger.warning("NASA Images: descarga de %s falló (%s)", url, exc)
                continue
            candidates.append(
                MediaCandidate(
                    path=dest,
                    title=data.get("title") or query,
                    source="nasa",
                    source_url=f"https://images.nasa.gov/details-{nasa_id}",
                    license="Dominio público (obra del gobierno de EE.UU.)",
                    author=data.get("photographer") or data.get("center"),
                )
            )
        return candidates
