from pathlib import Path

import pytest

from illustrated_narrator.adapters.publish.tiktok_publisher import TikTokPublisher


class _FakeResponse:
    def __init__(self, status_code: int = 200, json_data=None, text: str = "") -> None:
        self.status_code = status_code
        self._json_data = json_data or {}
        self.text = text

    def json(self):
        return self._json_data


class _FakeSession:
    def __init__(self, init_response: _FakeResponse, put_response: _FakeResponse | None = None) -> None:
        self._init_response = init_response
        self._put_response = put_response or _FakeResponse(200)
        self.post_calls: list[dict] = []
        self.put_calls: list[dict] = []

    def post(self, url, json=None, headers=None, timeout=None):
        self.post_calls.append({"url": url, "json": json, "headers": headers})
        return self._init_response

    def put(self, url, data=None, headers=None, timeout=None):
        self.put_calls.append({"url": url, "data": data, "headers": headers})
        return self._put_response


_OK_INIT = _FakeResponse(
    200, {"data": {"publish_id": "v_pub_123", "upload_url": "https://upload.example/x"}, "error": {"code": "ok"}}
)


def test_is_available_requires_access_token() -> None:
    assert TikTokPublisher(None).is_available() is False
    assert TikTokPublisher("token").is_available() is True


def test_publish_raises_when_not_configured(tmp_path: Path) -> None:
    video = tmp_path / "final.mp4"
    video.write_bytes(b"x")
    with pytest.raises(RuntimeError, match="Falta NARR_TIKTOK"):
        TikTokPublisher(None).publish(video, title="", description="")


def test_publish_raises_on_missing_video(tmp_path: Path) -> None:
    publisher = TikTokPublisher("token", session=_FakeSession(_OK_INIT))
    with pytest.raises(RuntimeError, match="No existe"):
        publisher.publish(tmp_path / "missing.mp4", title="", description="")


def test_publish_video_chico_va_en_un_solo_chunk(tmp_path: Path) -> None:
    video = tmp_path / "final.mp4"
    video.write_bytes(b"x" * 1000)
    session = _FakeSession(_OK_INIT)
    publisher = TikTokPublisher("token", session=session)

    result = publisher.publish(video, title="Mi video", description="desc")

    assert result.post_id == "v_pub_123"
    # init: un solo chunk, tamaño = archivo entero
    init_body = session.post_calls[0]["json"]
    assert init_body["source_info"]["total_chunk_count"] == 1
    assert init_body["source_info"]["chunk_size"] == 1000
    assert init_body["source_info"]["video_size"] == 1000
    assert init_body["post_info"]["privacy_level"] == "SELF_ONLY"  # default seguro
    assert init_body["post_info"]["title"] == "Mi video"
    # un solo PUT con el archivo completo
    assert len(session.put_calls) == 1
    assert session.put_calls[0]["headers"]["Content-Range"] == "bytes 0-999/1000"


def test_publish_video_grande_se_parte_en_varios_chunks_bajo_64mb(tmp_path: Path) -> None:
    # 130MB -> no puede ir en un solo chunk (máximo de TikTok: 64MB) --
    # confirma que se parte y que NINGÚN chunk (incluido el último) supera
    # el límite documentado.
    video = tmp_path / "final.mp4"
    video_size = 130_000_000
    with video.open("wb") as f:
        f.seek(video_size - 1)
        f.write(b"\0")
    session = _FakeSession(_OK_INIT)
    publisher = TikTokPublisher("token", session=session)

    publisher.publish(video, title="x", description="")

    init_body = session.post_calls[0]["json"]
    chunk_size = init_body["source_info"]["chunk_size"]
    total_chunks = init_body["source_info"]["total_chunk_count"]
    assert chunk_size <= 64_000_000
    assert total_chunks > 1
    assert len(session.put_calls) == total_chunks
    # el último chunk (el que más riesgo tiene de pasarse) también respeta el límite
    last_range = session.put_calls[-1]["headers"]["Content-Range"]
    last_start, rest = last_range.replace("bytes ", "").split("-")
    last_end = rest.split("/")[0]
    assert (int(last_end) - int(last_start) + 1) <= 64_000_000
    # los chunks cubren el archivo completo sin huecos ni superposición
    assert last_end == str(video_size - 1)


def test_publish_respeta_privacy_level_configurado(tmp_path: Path) -> None:
    video = tmp_path / "final.mp4"
    video.write_bytes(b"x")
    session = _FakeSession(_OK_INIT)
    publisher = TikTokPublisher("token", privacy_level="PUBLIC_TO_EVERYONE", session=session)

    publisher.publish(video, title="", description="")

    assert session.post_calls[0]["json"]["post_info"]["privacy_level"] == "PUBLIC_TO_EVERYONE"


def test_init_falla_lanza_con_el_error_de_tiktok(tmp_path: Path) -> None:
    video = tmp_path / "final.mp4"
    video.write_bytes(b"x")
    session = _FakeSession(
        _FakeResponse(403, {"error": {"code": "unaudited_client_can_only_post_to_private_accounts"}})
    )
    publisher = TikTokPublisher("token", privacy_level="PUBLIC_TO_EVERYONE", session=session)

    with pytest.raises(RuntimeError, match="unaudited_client_can_only_post_to_private_accounts"):
        publisher.publish(video, title="", description="")


def test_chunk_upload_fallido_lanza(tmp_path: Path) -> None:
    video = tmp_path / "final.mp4"
    video.write_bytes(b"x" * 1000)
    session = _FakeSession(_OK_INIT, put_response=_FakeResponse(500, text="server error"))
    publisher = TikTokPublisher("token", session=session)

    with pytest.raises(RuntimeError, match="chunk 1/1"):
        publisher.publish(video, title="", description="")
