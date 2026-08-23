"""Cliente de la API pública de Openverse — sin API key.

Openverse (openverse.org, ex CC Search) agrega contenido con licencia abierta
(CC0, dominio público, CC-BY, CC-BY-SA) de decenas de fuentes (Flickr,
museos, Wikimedia, etc.) bajo una sola búsqueda. Buena fuente adicional
gratuita para ampliar lo que Pexels/Wikimedia no encuentran solos.
"""

import logging
import time
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from illustrated_narrator.adapters.media._http_hard_timeout import call_with_hard_timeout
from illustrated_narrator.ports.stock_media import MediaCandidate, StockImagePort

logger = logging.getLogger(__name__)

_TIMEOUT = 15
# Timeout duro (cubre DNS colgado, ver _http_hard_timeout.py) para la llamada
# que abre la conexión -- una vez con headers recibidos, el resto ya está
# acotado por _TIMEOUT (reads) y _MAX_DOWNLOAD_SECONDS (streaming).
_HARD_TIMEOUT = 20
_API_URL = "https://api.openverse.org/v1/images/"
# Mismo motivo que en wikimedia_adapter.py: algunas fuentes agregadas por
# Openverse sirven escaneos/fotos de altísima resolución que no aportan nada
# para un cutaway de unos pocos segundos y solo alargan la descarga.
_MAX_DOWNLOAD_BYTES = 20_000_000
# El tope de bytes no alcanza solo: un archivo CHICO que gotea muy lento
# nunca llega a _MAX_DOWNLOAD_BYTES y el timeout de requests se reinicia con
# cada byte recibido, así que nunca se dispara (mismo bug ya documentado en
# wikimedia_adapter.py para archivos grandes, pero este caso es un archivo
# cualquiera con conexión lenta -- confirmado en una corrida real: colgó la
# investigación de medios sin CPU y sin progreso por más de 10 minutos).
_MAX_DOWNLOAD_SECONDS = 20
_ALLOWED_EXTENSIONS = (".jpg", ".jpeg", ".png")
# Openverse agrega archivos alojados en la CDN de Wikimedia (upload.wikimedia
# .org) sin pasar por su propia CDN -- esas descargas compiten con las de
# WikimediaCommonsAdapter por el mismo host y, sin throttle propio acá,
# aceleran el 403 por carga (ver wikimedia_adapter.py, mismo síntoma
# confirmado en una corrida real: 403 repetido en archivos que sí existen y
# son públicos, se resuelven solos con reintento/espera).
_MIN_INTERVAL_SECONDS = 1.0


class OpenverseAdapter(StockImagePort):
    def __init__(self, session: requests.Session | None = None) -> None:
        self._http = session or requests.Session()
        retry = Retry(
            total=2, backoff_factor=2.0, status_forcelist=(403, 429, 503),
            respect_retry_after_header=True, allowed_methods=("GET",),
        )
        adapter = HTTPAdapter(max_retries=retry)
        self._http.mount("https://", adapter)
        self._http.mount("http://", adapter)
        self._last_request_at = 0.0

    def is_available(self) -> bool:
        return True  # API pública, sin key

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < _MIN_INTERVAL_SECONDS:
            time.sleep(_MIN_INTERVAL_SECONDS - elapsed)
        self._last_request_at = time.monotonic()

    def _download_capped(self, url: str, dest: Path) -> bool:
        # Muchos resultados de Openverse apuntan directo a upload.wikimedia
        # .org -- ese host devuelve 403 en conexiones REUTILIZADAS de una
        # misma Session (keep-alive), no por cookies ni volumen (ver el fix
        # real y cómo se confirmó en wikimedia_adapter.py). Connection:
        # close fuerza una conexión nueva por descarga.
        self._http.cookies.clear()
        start = time.monotonic()
        self._throttle()
        resp = call_with_hard_timeout(
            lambda: self._http.get(
                url, timeout=_TIMEOUT, stream=True, headers={"Connection": "close"}
            ),
            _HARD_TIMEOUT,
        )
        with resp:
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
                if time.monotonic() - start > _MAX_DOWNLOAD_SECONDS:
                    return False
                chunks.append(chunk)
        dest.write_bytes(b"".join(chunks))
        return True

    def search(self, query: str, dest_dir: Path, count: int) -> list[MediaCandidate]:
        if not query.strip():
            return []
        try:
            resp = call_with_hard_timeout(
                lambda: self._http.get(
                    _API_URL,
                    params={
                        "q": query,
                        "page_size": count,
                        "mature": "false",
                    },
                    headers={"User-Agent": "illustrated-narrator/1.0 (local tool, single user)"},
                    timeout=_TIMEOUT,
                ),
                _HARD_TIMEOUT,
            )
            resp.raise_for_status()
            results = resp.json().get("results", [])
        except (requests.RequestException, ValueError, TimeoutError) as exc:
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
            except (requests.RequestException, TimeoutError) as exc:
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
