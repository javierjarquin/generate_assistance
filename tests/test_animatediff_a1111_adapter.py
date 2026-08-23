import base64
from pathlib import Path

from illustrated_narrator.adapters.video.animatediff_a1111_adapter import AnimateDiffA1111Adapter
from illustrated_narrator.ports.video_generator import VideoGenerationRequest

_FAKE_MP4 = b"\x00\x00\x00\x18ftypmp42" + b"fake-mp4-bytes"


class _FakeResponse:
    def __init__(self, json_data=None, ok: bool = True) -> None:
        self._json_data = json_data
        self.ok = ok

    def raise_for_status(self) -> None:
        pass

    def json(self):
        return self._json_data


class _FakeSession:
    def __init__(self, txt2img_json=None, options_ok: bool = True) -> None:
        self._txt2img_json = txt2img_json
        self._options_ok = options_ok
        self.posts: list[tuple[str, dict]] = []

    def get(self, url, timeout=None):
        return _FakeResponse(ok=self._options_ok)

    def post(self, url, json=None, timeout=None):
        self.posts.append((url, json))
        return _FakeResponse(json_data=self._txt2img_json)


def test_is_available_true_si_responde_ok():
    adapter = AnimateDiffA1111Adapter("http://127.0.0.1:7860", session=_FakeSession(options_ok=True))
    assert adapter.is_available() is True


def test_is_available_false_si_no_responde_ok():
    adapter = AnimateDiffA1111Adapter("http://127.0.0.1:7860", session=_FakeSession(options_ok=False))
    assert adapter.is_available() is False


def test_generate_escribe_el_mp4_devuelto(tmp_path: Path) -> None:
    b64 = base64.b64encode(_FAKE_MP4).decode()
    session = _FakeSession(txt2img_json={"images": [b64]})
    adapter = AnimateDiffA1111Adapter("http://127.0.0.1:7860", session=session)
    dest = tmp_path / "media" / "videos" / "p06.mp4"

    request = VideoGenerationRequest(prompt="dark prison cell block", duration_seconds=4.0, fps=8)
    result = adapter.generate(request, dest)

    assert result == dest
    assert dest.read_bytes() == _FAKE_MP4


def test_generate_arma_el_payload_con_animatediff_alwayson_y_modulo_estandar(tmp_path: Path) -> None:
    b64 = base64.b64encode(_FAKE_MP4).decode()
    session = _FakeSession(txt2img_json={"images": [b64]})
    adapter = AnimateDiffA1111Adapter("http://127.0.0.1:7860", session=session)
    dest = tmp_path / "p06.mp4"

    adapter.generate(VideoGenerationRequest(prompt="x", duration_seconds=4.0, fps=8), dest)

    url, payload = session.posts[0]
    assert url.endswith("/sdapi/v1/txt2img")
    # Módulo estándar, NO AnimateLCM -- confirmado en pruebas reales que
    # AnimateLCM colapsa en ruido para contenido de bajo detalle (logos,
    # fondos casi sólidos), justo lo que más necesita este fallback.
    assert payload["sampler_name"] == "Euler a"
    assert payload["steps"] == 20
    assert payload["cfg_scale"] == 7
    assert "<lora:" not in payload["prompt"]
    ad_args = payload["alwayson_scripts"]["AnimateDiff"]["args"][0]
    assert ad_args["model"] == "mm_sd15_v2.safetensors"
    assert ad_args["enable"] is True
    assert ad_args["video_length"] == 32  # 4.0s * 8fps
    assert ad_args["fps"] == 8


def test_generate_falla_si_no_hay_mp4_en_la_respuesta(tmp_path: Path) -> None:
    session = _FakeSession(txt2img_json={"images": []})
    adapter = AnimateDiffA1111Adapter("http://127.0.0.1:7860", session=session)
    try:
        adapter.generate(VideoGenerationRequest(prompt="x"), tmp_path / "p06.mp4")
        assert False, "debía lanzar"
    except RuntimeError as exc:
        assert "no devolvió un MP4" in str(exc)
