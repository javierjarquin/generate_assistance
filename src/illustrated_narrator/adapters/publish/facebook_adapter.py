"""Publica video en una Página de Facebook via Graph API.

Requiere un Token de Acceso de Página (Page Access Token) con permiso
pages_manage_posts -- se genera desde developers.facebook.com/tools/explorer
(o via un token de usuario intercambiado por uno de página de larga
duración). Sin OAuth interactivo acá: el token ya viene resuelto desde la
config, igual que las keys de Pexels/Freesound.
"""

import logging
from pathlib import Path

import requests

from illustrated_narrator.ports.publisher import PublishResult, VideoPublisherPort

logger = logging.getLogger(__name__)

_TIMEOUT = 300  # video puede tardar en subir; timeout generoso
_API_VERSION = "v21.0"


class FacebookPagePublisher(VideoPublisherPort):
    def __init__(
        self,
        page_id: str | None,
        access_token: str | None,
        session: requests.Session | None = None,
    ) -> None:
        self._page_id = page_id or ""
        self._access_token = access_token or ""
        self._http = session or requests.Session()

    def is_available(self) -> bool:
        return bool(self._page_id and self._access_token)

    def publish(self, video_path: Path, title: str, description: str) -> PublishResult:
        if not self.is_available():
            raise RuntimeError(
                "Falta NARR_FACEBOOK_PAGE_ID o NARR_FACEBOOK_PAGE_ACCESS_TOKEN en .env"
            )
        if not video_path.exists():
            raise RuntimeError(f"No existe el video a publicar: {video_path}")

        url = f"https://graph-video.facebook.com/{_API_VERSION}/{self._page_id}/videos"
        data = {
            "access_token": self._access_token,
            "description": description,
        }
        if title:
            data["title"] = title

        with video_path.open("rb") as fh:
            files = {"source": (video_path.name, fh, "video/mp4")}
            try:
                resp = self._http.post(url, data=data, files=files, timeout=_TIMEOUT)
            except requests.RequestException as exc:
                raise RuntimeError(f"Facebook: falló la conexión ({exc})") from exc

        if resp.status_code != 200:
            try:
                err = resp.json().get("error", {}).get("message", resp.text)
            except ValueError:
                err = resp.text
            raise RuntimeError(f"Facebook: publicación falló ({resp.status_code}): {err}")

        body = resp.json()
        video_id = body.get("id", "")
        page_url = f"https://www.facebook.com/{self._page_id}/videos/{video_id}" if video_id else None
        logger.info("Publicado en Facebook: %s", page_url or video_id)
        return PublishResult(post_id=video_id, url=page_url)
