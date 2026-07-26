"""Cliente de la API pública de Wikimedia Commons — sin API key.

Mejor fuente para material documental/histórico real (fotos de archivo,
mapas, imágenes científicas de dominio público o CC). La licencia varía por
archivo y se lee de `extmetadata` — importante porque CC-BY-SA exige
atribución (a diferencia de Pexels).
"""

import logging
import time
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from illustrated_narrator.ports.stock_media import MediaCandidate, StockImagePort

logger = logging.getLogger(__name__)

_TIMEOUT = 15
_API_URL = "https://commons.wikimedia.org/w/api.php"
_ALLOWED_EXTENSIONS = (".jpg", ".jpeg", ".png")
# Wikimedia sirve muchos archivos de archivo/científicos como escaneos de
# altísima resolución (decenas de MB) -- visto en corridas reales: una
# descarga de 66MB+ tardó tanto que colgó la investigación de medios varios
# minutos sin ningún progreso visible (el timeout de requests reinicia con
# cada byte recibido, así que un goteo lento nunca lo dispara). Subido de 8MB
# a 20MB (a pedido, para no perderse fotos de archivo/científicas de buena
# calidad que sí superan 8MB) -- sigue habiendo tope porque sin él el mismo
# problema real (66MB+) vuelve a colgar la investigación; se descarga en
# streaming y se aborta si supera el tope, sea por Content-Length o durante
# la lectura, así que el corte es inmediato, no una espera larga.
_MAX_DOWNLOAD_BYTES = 20_000_000
# Wikimedia bloquea con 403 las peticiones sin User-Agent descriptivo
# (https://meta.wikimedia.org/wiki/User-Agent_policy) — requests manda uno
# genérico por defecto.
_USER_AGENT = "illustrated-narrator/1.0 (https://github.com/; local tool, single user)"
# Sin key, el límite anónimo de Wikimedia se satura rápido con 34 planos x 3
# candidatos (visto en corrida real: 429 sostenido en cascada). Throttle fijo
# entre requests + un reintento acotado que respeta Retry-After evita tanto
# el 429 en cascada como un reintento sin límite que cuelgue la investigación.
_MIN_INTERVAL_SECONDS = 1.5


class WikimediaCommonsAdapter(StockImagePort):
    def __init__(self, session: requests.Session | None = None) -> None:
        self._http = session or requests.Session()
        # requests.Session ya trae su propio User-Agent por defecto
        # (python-requests/x.x) -- hay que pisarlo, no basta con setdefault.
        self._http.headers["User-Agent"] = _USER_AGENT
        retry = Retry(
            total=2, backoff_factor=2.0, status_forcelist=(429, 503),
            respect_retry_after_header=True, allowed_methods=("GET",),
        )
        adapter = HTTPAdapter(max_retries=retry)
        self._http.mount("https://", adapter)
        self._http.mount("http://", adapter)
        self._last_request_at = 0.0

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < _MIN_INTERVAL_SECONDS:
            time.sleep(_MIN_INTERVAL_SECONDS - elapsed)
        self._last_request_at = time.monotonic()

    def is_available(self) -> bool:
        return True  # API pública, sin key

    def _download_capped(self, url: str, dest: Path) -> bool:
        """Descarga en streaming, abortando si supera _MAX_DOWNLOAD_BYTES (por
        Content-Length o durante la lectura, si el header falta o miente).
        True si se descargó completo, False si se saltó por tamaño."""
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
            self._throttle()
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
                self._throttle()
                if not self._download_capped(url, dest):
                    logger.info(
                        "Wikimedia Commons: %s superó %dMB, se salta (no es necesario "
                        "tanta resolución para un cutaway)", url, _MAX_DOWNLOAD_BYTES // 1_000_000,
                    )
                    continue
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
