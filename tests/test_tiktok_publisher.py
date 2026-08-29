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


def _rangos(session: "_FakeSession") -> list[tuple[int, int]]:
    """(primer_byte, ultimo_byte) de cada Content-Range enviado."""
    out = []
    for call in session.put_calls:
        rango = call["headers"]["Content-Range"].replace("bytes ", "")
        inicio, resto = rango.split("-")
        out.append((int(inicio), int(resto.split("/")[0])))
    return out


def test_publish_video_grande_respeta_la_formula_de_chunks_de_tiktok(tmp_path: Path) -> None:
    # Regla real de TikTok: total_chunk_count = floor(video_size/chunk_size),
    # y el ÚLTIMO chunk absorbe los bytes sobrantes (puede pasar chunk_size,
    # hasta 128MB). Antes se declaraba ceil() y la API rechazaba la subida con
    # "The total chunk count is invalid" -- reproducido con un video real de
    # 131MB: el código mandaba 3 y TikTok esperaba 2.
    video = tmp_path / "final.mp4"
    video_size = 137_555_863  # tamaño real de guion-campo-algodonero
    with video.open("wb") as f:
        f.seek(video_size - 1)
        f.write(b"\0")
    session = _FakeSession(_OK_INIT)

    TikTokPublisher("token", session=session).publish(video, title="x", description="")

    source = session.post_calls[0]["json"]["source_info"]
    chunk_size = source["chunk_size"]
    total_chunks = source["total_chunk_count"]

    assert total_chunks == video_size // chunk_size
    assert total_chunks > 1
    assert 5_000_000 <= chunk_size <= 64_000_000
    assert len(session.put_calls) == total_chunks

    rangos = _rangos(session)
    # Cubren el archivo entero, sin huecos ni superposición.
    assert rangos[0][0] == 0
    assert rangos[-1][1] == video_size - 1
    for (_, fin_previo), (inicio, _) in zip(rangos, rangos[1:]):
        assert inicio == fin_previo + 1
    # El último chunk se pasa de chunk_size (absorbe la cola) pero no de 128MB.
    ultimo = rangos[-1][1] - rangos[-1][0] + 1
    assert ultimo > chunk_size
    assert ultimo <= 128_000_000


def test_chunk_plan_coincide_con_floor_para_varios_tamanos() -> None:
    for size in (4_000_000, 57_000_000, 57_000_001, 114_000_001, 137_555_863, 500_000_000):
        chunk_size, total = TikTokPublisher._chunk_plan(size)
        assert 0 < chunk_size <= 64_000_000, size
        if size <= chunk_size:
            assert total == 1, size
        else:
            assert total == size // chunk_size, size
            assert size - (total - 1) * chunk_size <= 128_000_000, size


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


# --- creator_info: base de la pantalla de confirmación que exige la auditoría ---

_CREATOR_OK = {
    "data": {
        "creator_username": "datomatagato",
        "creator_nickname": "Dato Mata Gato",
        "creator_avatar_url": "https://cdn/avatar.jpg",
        "privacy_level_options": ["PUBLIC_TO_EVERYONE", "SELF_ONLY"],
        "comment_disabled": False,
        "duet_disabled": True,
        "stitch_disabled": False,
        "max_video_post_duration_sec": 600,
    },
    "error": {"code": "ok"},
}


def test_creator_info_parsea_la_configuracion_de_la_cuenta() -> None:
    session = _FakeSession(_FakeResponse(200, _CREATOR_OK))
    publisher = TikTokPublisher(access_token="tok", session=session)

    info = publisher.query_creator_info()

    assert info.username == "datomatagato"
    assert info.nickname == "Dato Mata Gato"
    assert info.privacy_level_options == ("PUBLIC_TO_EVERYONE", "SELF_ONLY")
    assert info.duet_disabled is True
    assert info.comment_disabled is False
    assert info.max_video_post_duration_sec == 600
    assert session.post_calls[0]["url"].endswith("/post/publish/creator_info/query/")


def test_creator_info_valida_el_nivel_de_privacidad() -> None:
    session = _FakeSession(_FakeResponse(200, _CREATOR_OK))
    info = TikTokPublisher(access_token="tok", session=session).query_creator_info()

    assert info.permite_privacidad("SELF_ONLY") is True
    assert info.permite_privacidad("PUBLIC_TO_EVERYONE") is True
    # Cuenta privada: ofrecer esto sería ignorar la config del creador, que
    # es una de las causas de rechazo de la auditoría.
    assert info.permite_privacidad("MUTUAL_FOLLOW_FRIENDS") is False


def test_creator_info_sin_token_lanza() -> None:
    publisher = TikTokPublisher(access_token=None)
    with pytest.raises(RuntimeError, match="NARR_TIKTOK_ACCESS_TOKEN"):
        publisher.query_creator_info()


def test_creator_info_propaga_el_error_de_tiktok() -> None:
    session = _FakeSession(
        _FakeResponse(401, {"error": {"code": "access_token_invalid", "message": "expired"}})
    )
    publisher = TikTokPublisher(access_token="vencido", session=session)

    with pytest.raises(RuntimeError, match="access_token_invalid"):
        publisher.query_creator_info()


def test_chunk_intermedio_con_206_no_es_error(tmp_path: Path) -> None:
    # 206 (Partial Content) es la respuesta de EXITO de TikTok para un chunk
    # intermedio. Tratarla como error cortaba la subida en el primer chunk de
    # todo video que necesitara partirse (visto en una subida real).
    video = tmp_path / "final.mp4"
    video_size = 137_555_863
    with video.open("wb") as f:
        f.seek(video_size - 1)
        f.write(b"\0")
    session = _FakeSession(_OK_INIT, put_response=_FakeResponse(206))

    TikTokPublisher("token", session=session).publish(video, title="x", description="")

    assert len(session.put_calls) == 2
