"""Cliente de la API pública de Wikipedia en español — sin API key.

A diferencia de WikimediaCommonsAdapter (que busca archivos directo en
Commons por palabra clave), esto busca el ARTÍCULO de Wikipedia más
relevante para la query y usa sus imágenes de contenido embebidas. Fuente
de último recurso: cubre nombres propios/temas concretos donde el archivo
en Commons no trae esas palabras en su título pero SÍ está enlazado desde
el artículo correspondiente (ej. el retrato de una persona en su ficha).
"""

import logging
import re
import time
from pathlib import Path
from urllib.parse import urlsplit

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from illustrated_narrator.adapters.media._http_hard_timeout import call_with_hard_timeout
from illustrated_narrator.ports.stock_media import MediaCandidate, StockImagePort

logger = logging.getLogger(__name__)

_TIMEOUT = 15
# Timeout duro (cubre DNS colgado) + tope de tiempo total de descarga (cubre
# un archivo chico con conexión lenta, que nunca llega a _MAX_DOWNLOAD_BYTES)
# -- mismo bug ya documentado y arreglado en wikimedia_adapter.py y
# openverse_adapter.py, misma causa (el timeout de requests no cubre ninguno
# de los dos casos).
_HARD_TIMEOUT = 20
_MAX_DOWNLOAD_SECONDS = 20
_API_URL = "https://es.wikipedia.org/w/api.php"
_ALLOWED_EXTENSIONS = (".jpg", ".jpeg", ".png")
# Mismo motivo que wikimedia_adapter.py: evitar escaneos/fotos de archivo de
# altísima resolución que solo alargan la descarga sin aportar a un cutaway.
_MAX_DOWNLOAD_BYTES = 20_000_000
_USER_AGENT = "illustrated-narrator/1.0 (https://github.com/; local tool, single user)"

# Iconos/logos de proyectos hermanos y de mantenimiento -- nunca son
# "contenido" del artículo aunque aparezcan en su lista de imágenes.
_RUIDO = re.compile(
    r"commons-logo|wikidata|wikibooks|wiktionary|wikiquote|wikisource|"
    r"wikiversity|wikivoyage|wikispecies|wikinews|wikimedia[-_]|"
    r"wikipedia[-_]?logo|padlock|ambox|question[_ ]book|nuvola|ooui|"
    r"edit-icon|folder icon|crystal_clear|gnome-|pictogram|"
    r"disambig|merge-arrow",
    re.IGNORECASE,
)


class WikipediaArticleAdapter(StockImagePort):
    def __init__(self, session: requests.Session | None = None, api_url: str = _API_URL) -> None:
        self._http = session or requests.Session()
        self._http.headers["User-Agent"] = _USER_AGENT
        self._api_url = api_url
        retry = Retry(
            total=2, backoff_factor=2.0, status_forcelist=(403, 429, 503),
            respect_retry_after_header=True, allowed_methods=("GET",),
        )
        adapter = HTTPAdapter(max_retries=retry)
        self._http.mount("https://", adapter)
        self._http.mount("http://", adapter)

    def is_available(self) -> bool:
        return True  # API pública, sin key

    def _get(self, params: dict) -> dict:
        resp = call_with_hard_timeout(
            lambda: self._http.get(self._api_url, params={**params, "format": "json"}, timeout=_TIMEOUT),
            _HARD_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()

    def _find_article_title(self, query: str) -> str | None:
        data = self._get({"action": "query", "list": "search", "srsearch": query, "srlimit": 1})
        resultados = data.get("query", {}).get("search", [])
        return resultados[0]["title"] if resultados else None

    def _content_image_titles(self, article_title: str) -> list[str]:
        data = self._get({
            "action": "query", "prop": "images", "imlimit": "max",
            "redirects": 1, "titles": article_title,
        })
        pagina = next(iter(data.get("query", {}).get("pages", {}).values()), {})
        return [i["title"] for i in pagina.get("images", []) if not _RUIDO.search(i["title"])]

    def _download_capped(self, url: str, dest: Path) -> bool:
        # Mismo fix real que wikimedia_adapter.py: upload.wikimedia.org
        # devuelve 403 en conexiones REUTILIZADAS de una misma Session
        # (keep-alive), no por cookies ni volumen -- Connection: close
        # fuerza una conexión nueva por descarga (confirmado con pruebas
        # reales aisladas).
        self._http.cookies.clear()
        start = time.monotonic()
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
            article_title = self._find_article_title(query)
        except (requests.RequestException, ValueError, TimeoutError) as exc:
            logger.warning("Wikipedia (artículo): búsqueda '%s' falló (%s)", query, exc)
            return []
        if not article_title:
            return []

        try:
            archivos = self._content_image_titles(article_title)
        except (requests.RequestException, ValueError, TimeoutError) as exc:
            logger.warning("Wikipedia (artículo): imágenes de '%s' fallaron (%s)", article_title, exc)
            return []
        if not archivos:
            return []

        dest_dir.mkdir(parents=True, exist_ok=True)
        candidates: list[MediaCandidate] = []
        for lote_inicio in range(0, len(archivos), 20):
            if len(candidates) >= count:
                break
            lote = "|".join(archivos[lote_inicio: lote_inicio + 20])
            try:
                data = self._get({
                    "action": "query", "prop": "imageinfo",
                    "iiprop": "url|extmetadata", "titles": lote,
                })
            except (requests.RequestException, ValueError, TimeoutError) as exc:
                logger.warning("Wikipedia (artículo): imageinfo falló (%s)", exc)
                continue
            for page in data.get("query", {}).get("pages", {}).values():
                if len(candidates) >= count:
                    break
                if page.get("imagerepository") != "shared":
                    continue  # solo Commons: licencia verificable, reutilizable
                infos = page.get("imageinfo") or []
                if not infos:
                    continue
                info = infos[0]
                url = info.get("url", "")
                url_path = urlsplit(url).path
                if not url_path.lower().endswith(_ALLOWED_EXTENSIONS):
                    continue
                meta = info.get("extmetadata", {})
                dest = dest_dir / f"wikipedia_{page.get('pageid', len(candidates))}{Path(url_path).suffix.lower()}"
                try:
                    if not self._download_capped(url, dest):
                        logger.info(
                            "Wikipedia (artículo): %s superó %dMB, se salta",
                            url, _MAX_DOWNLOAD_BYTES // 1_000_000,
                        )
                        continue
                except (requests.RequestException, TimeoutError) as exc:
                    logger.warning("Wikipedia (artículo): descarga de %s falló (%s)", url, exc)
                    continue
                candidates.append(
                    MediaCandidate(
                        path=dest,
                        title=page.get("title", article_title),
                        source="wikipedia_articulo",
                        source_url=f"https://es.wikipedia.org/wiki/{article_title.replace(' ', '_')}",
                        license=meta.get("LicenseShortName", {}).get("value", "ver página de origen"),
                        author=meta.get("Artist", {}).get("value"),
                    )
                )
        return candidates
