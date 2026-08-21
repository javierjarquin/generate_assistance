"""Cliente de la API pública de Openverse — sin API key.

Openverse (openverse.org, ex CC Search) agrega contenido con licencia abierta
(CC0, dominio público, CC-BY, CC-BY-SA) de decenas de fuentes (Flickr,
museos, Wikimedia, etc.) bajo una sola búsqueda. Buena fuente adicional
gratuita para ampliar lo que Pexels/Wikimedia no encuentran solos.
"""

import logging
from pathlib import Path

import requests

from illustrated_narrator.ports.stock_media import MediaCandidate, StockImagePort

logger = logging.getLogger(__name__)

_TIMEOUT = 15
_API_URL = "https://api.openverse.org/v1/images/"
# Mismo motivo que en wikimedia_adapter.py: algunas fuentes agregadas por
# Openverse sirven escaneos/fotos de altísima resolución que no aportan nada
# para un cutaway de unos pocos segundos y solo alargan la descarga.
_MAX_DOWNLOAD_BYTES = 20_000_000
_ALLOWED_EXTENSIONS = (".jpg", ".jpeg", ".png")


class OpenverseAdapter(StockImagePort):
    def __init__(self, session: requests.Session | None = None) -> None:
        self._http = session or requests.Session()

    def is_available(self) -> bool:
        return True  # API pública, sin key

    def _download_capped(self, url: str, dest: Path) -> bool:
        with self._http.get(url, timeout=_TIMEOUT, stream=True) as resp:
            resp.raise_for_status()
            content_length = resp.headers.get("Content-Length")
            if content_length and int(content_length) > _MAX_DOWNLOAD_BYTES:
                return False
            written = 0
            chunks: list[bytes] = []
            for chunk in resp.iter_content(chunk_size=262_144):
                written += len(chunk)
                if written > _MAX_DOWNLOAD_BYTES:
                    return False
                chunks.append(chunk)
        dest.write_bytes(b"".join(chunks))
        return True

    def search(self, query: str, dest_dir: Path, count: int) -> list[MediaCandidate]:
        if not query.strip():
            return []
        try:
            resp = self._http.get(
                _API_URL,
                params={
                    "q": query,
                    "page_size": count,
                    "mature": "false",
                },
                headers={"User-Agent": "illustrated-narrator/1.0 (local tool, single user)"},
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
            results = resp.json().get("results", [])
        except (requests.RequestException, ValueError) as exc:
            logger.warning("Openverse: búsqueda '%s' falló (%s)", query, exc)
            return []

        dest_dir.mkdir(parents=True, exist_ok=True)
        candidates: list[MediaCandidate] = []
        for item in results:
            url = item.get("url") or ""
            filetype = (item.get("filetype") or "").lower()
            suffix = f".{filetype}" if filetype else Path(url).suffix.lower()
            if suffix not in _ALLOWED_EXTENSIONS:
                continue
            item_id = item.get("id", "")
            dest = dest_dir / f"openverse_{item_id}{suffix}"
            try:
                if not self._download_capped(url, dest):
                    logger.info(
                        "Openverse: %s superó %dMB, se salta (no es necesario "
                        "tanta resolución para un cutaway)", url, _MAX_DOWNLOAD_BYTES // 1_000_000,
                    )
                    continue
            except requests.RequestException as exc:
                logger.warning("Openverse: descarga de %s falló (%s)", url, exc)
                continue
            license_name = item.get("license", "").upper()
            license_version = item.get("license_version", "")
            candidates.append(
                MediaCandidate(
                    path=dest,
                    title=item.get("title") or query,
                    source="openverse",
                    source_url=item.get("foreign_landing_url") or item.get("detail_url", ""),
                    license=f"CC {license_name} {license_version}".strip(),
                    author=item.get("creator"),
                )
            )
        return candidates
