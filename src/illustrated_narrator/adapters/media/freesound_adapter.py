"""Cliente de la API de Freesound (música ambiental y SFX reales, CC0/CC-BY).

Key gratuita en freesound.org/apiv2/apply. Se descarga el preview mp3 (no
requiere OAuth, a diferencia del archivo original en alta calidad) — de sobra
para una cama de audio de fondo.
"""

import logging
from pathlib import Path

import requests

from illustrated_narrator.ports.stock_audio import StockAudioPort
from illustrated_narrator.ports.stock_media import MediaCandidate

logger = logging.getLogger(__name__)

_TIMEOUT = 15


class FreesoundAdapter(StockAudioPort):
    def __init__(self, api_key: str | None, session: requests.Session | None = None) -> None:
        self._api_key = api_key or ""
        self._http = session or requests.Session()

    def is_available(self) -> bool:
        return bool(self._api_key)

    def find(self, query: str, dest_dir: Path, kind: str) -> MediaCandidate | None:
        if not self._api_key or not query.strip():
            return None
        try:
            resp = self._http.get(
                "https://freesound.org/apiv2/search/text/",
                params={
                    "query": query,
                    "token": self._api_key,
                    "fields": "id,name,previews,license,username,url",
                    "filter": "duration:[10 TO 120]",
                    "sort": "score",
                    "page_size": 5,
                },
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
            results = resp.json().get("results", [])
        except (requests.RequestException, ValueError) as exc:
            logger.warning("Freesound: búsqueda '%s' falló (%s)", query, exc)
            return None
        if not results:
            return None

        sound = results[0]
        preview_url = (sound.get("previews") or {}).get("preview-hq-mp3")
        if not preview_url:
            return None

        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / f"freesound_{kind}_{sound['id']}.mp3"
        try:
            audio_resp = self._http.get(preview_url, timeout=_TIMEOUT)
            audio_resp.raise_for_status()
            dest.write_bytes(audio_resp.content)
        except requests.RequestException as exc:
            logger.warning("Freesound: descarga de %s falló (%s)", preview_url, exc)
            return None

        return MediaCandidate(
            path=dest,
            title=sound.get("name", query),
            source="freesound",
            source_url=sound.get("url", preview_url),
            license=sound.get("license", "ver página de origen"),
            author=sound.get("username"),
        )
