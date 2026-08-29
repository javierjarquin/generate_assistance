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
from dataclasses import dataclass
from pathlib import Path

import requests

from illustrated_narrator.ports.publisher import PublishResult, VideoPublisherPort

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CreatorInfo:
    """Respuesta de /v2/post/publish/creator_info/query/.

    La auditoría de TikTok exige que la pantalla de confirmación se arme a
    partir de esto y RESPETE la configuración del creador: ofrecer una
    opción de privacidad que no esté en `privacy_level_options`, o permitir
    comentarios cuando el creador los tiene deshabilitados, es una de las
    causas de rechazo más comunes.
    """

    username: str
    nickname: str
    avatar_url: str
    privacy_level_options: tuple[str, ...]
    comment_disabled: bool
    duet_disabled: bool
    stitch_disabled: bool
    max_video_post_duration_sec: int

    def permite_privacidad(self, nivel: str) -> bool:
        return nivel in self.privacy_level_options

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

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json; charset=UTF-8",
        }

    def query_creator_info(self) -> CreatorInfo:
        """Consulta la configuración actual del creador. Se usa para armar la
        pantalla de confirmación y para validar el nivel de privacidad ANTES
        de subir nada -- requisito de la auditoría de TikTok."""
        if not self.is_available():
            raise RuntimeError("Falta NARR_TIKTOK_ACCESS_TOKEN en .env (ver tools/tiktok_auth.py)")
        try:
            resp = self._http.post(
                f"{_API_BASE}/post/publish/creator_info/query/",
                headers=self._headers(), timeout=_TIMEOUT,
            )
        except requests.RequestException as exc:
            raise RuntimeError(f"TikTok: falló creator_info ({exc})") from exc

        try:
            body = resp.json()
        except ValueError:
            raise RuntimeError(
                f"TikTok: creator_info devolvió {resp.status_code} sin JSON: {resp.text[:500]}"
            )

        error = body.get("error") or {}
        if resp.status_code != 200 or error.get("code") not in (None, "ok"):
            raise RuntimeError(f"TikTok: creator_info falló ({resp.status_code}): {error}")

        data = body.get("data") or {}
        return CreatorInfo(
            username=data.get("creator_username", ""),
            nickname=data.get("creator_nickname", ""),
            avatar_url=data.get("creator_avatar_url", ""),
            privacy_level_options=tuple(data.get("privacy_level_options") or ()),
            comment_disabled=bool(data.get("comment_disabled")),
            duet_disabled=bool(data.get("duet_disabled")),
            stitch_disabled=bool(data.get("stitch_disabled")),
            max_video_post_duration_sec=int(data.get("max_video_post_duration_sec") or 0),
        )

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
        """(chunk_size, total_chunks) según la regla real de TikTok:

            total_chunk_count = floor(video_size / chunk_size)

        y el ÚLTIMO chunk absorbe los bytes sobrantes (puede superar
        chunk_size, hasta 128MB).

        Antes acá se hacía división por techo para que ningún chunk pasara
        el máximo. Eso daba un total_chunk_count mayor al que TikTok calcula
        y la API lo rechazaba con `invalid_params: The total chunk count is
        invalid` -- confirmado en una subida real de 131MB: el código
        declaraba 3 chunks y TikTok esperaba 2.
        """
        if video_size <= _CHUNK_SIZE:
            return video_size, 1
        return _CHUNK_SIZE, video_size // _CHUNK_SIZE

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
        try:
            resp = self._http.post(
                f"{_API_BASE}/post/publish/video/init/", json=payload,
                headers=self._headers(), timeout=_TIMEOUT,
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
                # El ÚLTIMO chunk llega hasta el final del archivo: con
                # total_chunk_count = floor(size/chunk_size), los bytes
                # sobrantes son parte del último chunk (TikTok lo permite
                # hasta 128MB). Cortarlo en chunk_size dejaba sin enviar la
                # cola del video.
                es_ultimo = i == total_chunks - 1
                end = (video_size if es_ultimo else start + chunk_size) - 1
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
