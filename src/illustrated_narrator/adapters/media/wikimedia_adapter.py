"""Cliente de la API pública de Wikimedia Commons — sin API key.

Mejor fuente para material documental/histórico real (fotos de archivo,
mapas, imágenes científicas de dominio público o CC). La licencia varía por
archivo y se lee de `extmetadata` — importante porque CC-BY-SA exige
atribución (a diferencia de Pexels).
"""

import logging
from pathlib import Path

import requests

from illustrated_narrator.ports.stock_media import MediaCandidate, StockImagePort

logger = logging.getLogger(__name__)

_TIMEOUT = 15
_API_URL = "https://commons.wikimedia.org/w/api.php"
_ALLOWED_EXTENSIONS = (".jpg", ".jpeg", ".png")
# Wikimedia bloquea con 403 las peticiones sin User-Agent descriptivo
# (https://meta.wikimedia.org/wiki/User-Agent_policy) — requests manda uno
# genérico por defecto.
_USER_AGENT = "illustrated-narrator/1.0 (https://github.com/; local tool, single user)"


class WikimediaCommonsAdapter(StockImagePort):
    def __init__(self, session: requests.Session | None = None) -> None:
        self._http = session or requests.Session()
        # requests.Session ya trae su propio User-Agent por defecto
        # (python-requests/x.x) -- hay que pisarlo, no basta con setdefault.
        self._http.headers["User-Agent"] = _USER_AGENT

    def is_available(self) -> bool:
        return True  # API pública, sin key

    def _query_pages(self, gsrsearch_terms: str, count: int) -> dict:
        params = {
            "action": "query",
            "generator": "search",
            "gsrsearch": f"filetype:bitmap {gsrsearch_terms}",
            "gsrnamespace": 6,  # File:
            "gsrlimit": count,
            "prop": "imageinfo",
            "iiprop": "url|extmetadata|user|mime",
            "format": "json",
        }
        try:
            resp = self._http.get(_API_URL, params=params, timeout=_TIMEOUT)
            resp.raise_for_status()
            return resp.json().get("query", {}).get("pages", {})
        except (requests.RequestException, ValueError) as exc:
            logger.warning("Wikimedia Commons: búsqueda '%s' falló (%s)", gsrsearch_terms, exc)
            return {}

    def search(self, query: str, dest_dir: Path, count: int) -> list[MediaCandidate]:
        if not query.strip():
            return []
        # CirrusSearch trata varias palabras como AND implícito: una query de
        # 4 términos casi siempre da 0 resultados aunque cada palabra exista
        # por separado. Se prueba con la query completa y, si no hay nada, se
        # acorta desde el final hasta 2 palabras antes de rendirse.
        words = query.split()
        pages: dict = {}
        for n in range(len(words), 0, -1):
            attempt = " ".join(words[:n])
            pages = self._query_pages(attempt, count)
            if pages:
                break
        if not pages:
            return []

        dest_dir.mkdir(parents=True, exist_ok=True)
        candidates: list[MediaCandidate] = []
        for page in pages.values():
            infos = page.get("imageinfo") or []
            if not infos:
                continue
            info = infos[0]
            url = info.get("url", "")
            if not url.lower().endswith(_ALLOWED_EXTENSIONS):
                continue
            meta = info.get("extmetadata", {})
            dest = dest_dir / f"wikimedia_{page['pageid']}{Path(url).suffix.lower()}"
            try:
                img_resp = self._http.get(url, timeout=_TIMEOUT)
                img_resp.raise_for_status()
                dest.write_bytes(img_resp.content)
            except requests.RequestException as exc:
                logger.warning("Wikimedia Commons: descarga de %s falló (%s)", url, exc)
                continue
            candidates.append(
                MediaCandidate(
                    path=dest,
                    title=page.get("title", query),
                    source="wikimedia",
                    source_url=f"https://commons.wikimedia.org/?curid={page['pageid']}",
                    license=meta.get("LicenseShortName", {}).get("value", "ver página de origen"),
                    author=meta.get("Artist", {}).get("value"),
                )
            )
        return candidates
