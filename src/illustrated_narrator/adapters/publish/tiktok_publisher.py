"""Publica video en TikTok via la Content Posting API (Direct Post).

Requiere OAuth por usuario (scope video.publish) -- ver
`tools/tiktok_auth.py` para la autorización única. Confirmado con la
documentación oficial (developers.tiktok.com, agosto 2026):

- Flujo de 2 pasos: POST /v2/post/publish/video/init/ (arma el post, pide
  privacy_level + tamaño/chunking del archivo) devuelve un upload_url;
  PUT del video (por chunks) a ese upload_url.
- Chunking (FILE_UPLOAD): cada chunk debe medir entre 5MB y 64MB, EXCEPTO
  que si el video entero pesa menos de 5MB va en un solo chunk igual. Acá
  se usa división por techo con chunks de ~57MB (bajo el máximo de 64MB)
  para que TODOS los chunks, incluido el último, cumplan el límite sin
  necesitar la excepción de "último chunk hasta 128MB" que documenta
  TikTok para otros esquemas de partición.
- **Mientras la app no esté auditada por TikTok, SOLO se puede publicar en
  modo privado** (`privacy_level=SELF_ONLY`) -- publicar público
  (`PUBLIC_TO_EVERYONE`) devuelve el error
  `unaudited_client_can_only_post_to_private_accounts` hasta que TikTok
  apruebe la app en su proceso de auditoría (fuera del alcance de este
  código -- ver README). Default acá: SELF_ONLY, a propósito.
"""

import logging
import math
from pathlib import Path

import requests

from illustrated_narrator.ports.publisher import PublishResult, VideoPublisherPort

logger = logging.getLogger(__name__)

_TIMEOUT = 300
_API_BASE = "https://open.tiktokapis.com/v2"
# Bajo el máximo de 64MB por chunk que exige TikTok -- con margen para no
# pisar el límite exacto por redondeos.
_CHUNK_SIZE = 57_000_000
_CONTENT_TYPE_BY_SUFFIX = {
    ".mp4": "video/mp4",
    ".mov": "video/quicktime",
    ".webm": "video/webm",
}


class TikTokPublisher(VideoPublisherPort):
    def __init__(
        self,
        access_token: str | None,
        privacy_level: str = "SELF_ONLY",
        session: requests.Session | None = None,
    ) -> None:
        self._access_token = access_token or ""
        self._privacy_level = privacy_level
        self._http = session or requests.Session()

    def is_available(self) -> bool:
        return bool(self._access_token)

    def publish(self, video_path: Path, title: str, description: str) -> PublishResult:
        if not self.is_available():
            raise RuntimeError("Falta NARR_TIKTOK_ACCESS_TOKEN en .env (ver tools/tiktok_auth.py)")
        if not video_path.exists():
            raise RuntimeError(f"No existe el video a publicar: {video_path}")

        video_size = video_path.stat().st_size
        chunk_size, total_chunks = self._chunk_plan(video_size)
        publish_id, upload_url = self._init_post(title or description, video_size, chunk_size, total_chunks)
        self._upload_chunks(video_path, upload_url, video_size, chunk_size, total_chunks)

        logger.info("Publicado en TikTok: %s (privacy=%s)", publish_id, self._privacy_level)
        return PublishResult(post_id=publish_id, url=None)

    @staticmethod
    def _chunk_plan(video_size: int) -> tuple[int, int]:
        """(chunk_size, total_chunks) -- división por techo: todos los
        chunks, incluido el último, quedan <= _CHUNK_SIZE (<=64MB exigido
        por TikTok), sin necesitar que el último absorba el resto."""
        if video_size <= _CHUNK_SIZE:
            return video_size, 1
        total_chunks = math.ceil(video_size / _CHUNK_SIZE)
        return math.ceil(video_size / total_chunks), total_chunks

    def _init_post(
        self, caption: str, video_size: int, chunk_size: int, total_chunks: int
    ) -> tuple[str, str]:
        payload = {
            "post_info": {
                "title": caption[:2200],
                "privacy_level": self._privacy_level,
            },
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": video_size,
                "chunk_size": chunk_size,
                "total_chunk_count": total_chunks,
            },
        }
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json; charset=UTF-8",
        }
        try:
            resp = self._http.post(
                f"{_API_BASE}/post/publish/video/init/", json=payload,
                headers=headers, timeout=_TIMEOUT,
            )
        except requests.RequestException as exc:
            raise RuntimeError(f"TikTok: falló init ({exc})") from exc

        try:
            body = resp.json()
        except ValueError:
            raise RuntimeError(f"TikTok: init devolvió {resp.status_code} sin JSON: {resp.text[:500]}")

        error = body.get("error") or {}
        if resp.status_code != 200 or error.get("code") not in (None, "ok"):
            raise RuntimeError(f"TikTok: init falló ({resp.status_code}): {error}")

        data = body.get("data") or {}
        publish_id = data.get("publish_id")
        upload_url = data.get("upload_url")
        if not publish_id or not upload_url:
            raise RuntimeError(f"TikTok: init no devolvió publish_id/upload_url: {body}")
        return publish_id, upload_url

    def _upload_chunks(
        self, video_path: Path, upload_url: str, video_size: int, chunk_size: int, total_chunks: int
    ) -> None:
        content_type = _CONTENT_TYPE_BY_SUFFIX.get(video_path.suffix.lower(), "video/mp4")
        with video_path.open("rb") as fh:
            for i in range(total_chunks):
                start = i * chunk_size
                end = min(start + chunk_size, video_size) - 1
                fh.seek(start)
                chunk = fh.read(end - start + 1)
                headers = {
                    "Content-Type": content_type,
                    "Content-Length": str(len(chunk)),
                    "Content-Range": f"bytes {start}-{end}/{video_size}",
                }
                try:
                    resp = self._http.put(upload_url, data=chunk, headers=headers, timeout=_TIMEOUT)
                except requests.RequestException as exc:
                    raise RuntimeError(
                        f"TikTok: falló subir chunk {i + 1}/{total_chunks} ({exc})"
                    ) from exc
                if resp.status_code not in (200, 201):
                    raise RuntimeError(
                        f"TikTok: chunk {i + 1}/{total_chunks} falló ({resp.status_code}): {resp.text[:500]}"
                    )
