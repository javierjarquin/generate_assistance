"""Cliente de la API de video de Pexels (B-roll real).

Misma key que las fotos (pexels.com/api), endpoint distinto. La API de video
no trae `alt`/tags como la de fotos — el único texto descriptivo disponible
es el slug de la URL pública (p.ej. ".../video/aerial-footage-of-a-town-2499611/"
-> "aerial footage of a town"), que se usa como título para que
`relevance_score` pueda puntuar el candidato igual que a una foto.
"""

import logging
import re
from pathlib import Path

import requests

from illustrated_narrator.ports.stock_media import MediaCandidate, StockImagePort

logger = logging.getLogger(__name__)

_TIMEOUT = 15
_DOWNLOAD_TIMEOUT = 60  # un mp4 pesa más que una respuesta JSON
_MAX_VIDEO_DURATION = 40  # segundos; evita bajar reels largos innecesariamente
_SLUG_RE = re.compile(r"/video/([a-z0-9-]+?)-\d+/?$", re.IGNORECASE)


def _slug_from_url(url: str) -> str:
    match = _SLUG_RE.search(url or "")
    if not match:
        return ""
    return match.group(1).replace("-", " ")


def _pick_video_file(files: list[dict], target_w: int) -> dict | None:
    mp4_files = [f for f in files if f.get("file_type") == "video/mp4" and f.get("link")]
    if not mp4_files:
        return None
    for quality in ("hd", "sd"):
        tier = [f for f in mp4_files if f.get("quality") == quality]
        if tier:
            return min(tier, key=lambda f: abs((f.get("width") or 0) - target_w))
    return min(mp4_files, key=lambda f: abs((f.get("width") or 0) - target_w))


class PexelsVideoAdapter(StockImagePort):
    def __init__(
        self, api_key: str | None, vertical: bool = False, session: requests.Session | None = None
    ) -> None:
        self._api_key = api_key or ""
        self._vertical = vertical
        self._http = session or requests.Session()

    def is_available(self) -> bool:
        return bool(self._api_key)

    def search(self, query: str, dest_dir: Path, count: int) -> list[MediaCandidate]:
        if not self._api_key or not query.strip():
            return []
        try:
            resp = self._http.get(
                "https://api.pexels.com/videos/search",
                headers={"Authorization": self._api_key},
                params={
                    "query": query,
                    "per_page": count,
                    "orientation": "portrait" if self._vertical else "landscape",
                },
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
            videos = resp.json().get("videos", [])
        except (requests.RequestException, ValueError) as exc:
            logger.warning("Pexels Video: búsqueda '%s' falló (%s)", query, exc)
            return []

        target_w = 1080 if self._vertical else 1920
        dest_dir.mkdir(parents=True, exist_ok=True)
        candidates: list[MediaCandidate] = []
        for video in videos:
            if (video.get("duration") or 0) > _MAX_VIDEO_DURATION:
                continue
            chosen_file = _pick_video_file(video.get("video_files", []), target_w)
            if chosen_file is None:
                continue
            dest = dest_dir / f"pexels_video_{video['id']}.mp4"
            try:
                video_resp = self._http.get(chosen_file["link"], timeout=_DOWNLOAD_TIMEOUT)
                video_resp.raise_for_status()
                dest.write_bytes(video_resp.content)
            except requests.RequestException as exc:
                logger.warning("Pexels Video: descarga de %s falló (%s)", chosen_file["link"], exc)
                continue
            page_url = video.get("url", chosen_file["link"])
            candidates.append(
                MediaCandidate(
                    path=dest,
                    title=_slug_from_url(page_url) or query,
                    source="pexels_video",
                    source_url=page_url,
                    license="Pexels License (uso libre, atribución no requerida)",
                    author=(video.get("user") or {}).get("name"),
                    media_type="video",
                )
            )
        return candidates
