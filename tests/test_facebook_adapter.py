from pathlib import Path

import pytest

from illustrated_narrator.adapters.publish.facebook_adapter import FacebookPagePublisher


class _FakeResponse:
    def __init__(self, status_code: int = 200, json_data=None, text: str = "") -> None:
        self.status_code = status_code
        self._json_data = json_data or {}
        self.text = text

    def json(self):
        return self._json_data


class _FakeSession:
    def __init__(self, response: _FakeResponse) -> None:
        self._response = response
        self.last_call: dict | None = None

    def post(self, url: str, data=None, files=None, timeout=None):
        self.last_call = {"url": url, "data": data, "files": files, "timeout": timeout}
        return self._response


def test_is_available_requires_page_id_and_token() -> None:
    assert FacebookPagePublisher(None, None).is_available() is False
    assert FacebookPagePublisher("123", None).is_available() is False
    assert FacebookPagePublisher(None, "token").is_available() is False
    assert FacebookPagePublisher("123", "token").is_available() is True


def test_publish_sends_video_and_returns_result(tmp_path: Path) -> None:
    video = tmp_path / "final.mp4"
    video.write_bytes(b"fake-video-bytes")
    session = _FakeSession(_FakeResponse(200, {"id": "999888777"}))
    publisher = FacebookPagePublisher("123456", "page-token", session=session)

    result = publisher.publish(video, title="Mi video", description="Un dato curioso")

    assert result.post_id == "999888777"
    assert result.url == "https://www.facebook.com/123456/videos/999888777"
    assert session.last_call is not None
    assert session.last_call["url"] == "https://graph-video.facebook.com/v21.0/123456/videos"
    assert session.last_call["data"]["access_token"] == "page-token"
    assert session.last_call["data"]["description"] == "Un dato curioso"
    assert session.last_call["data"]["title"] == "Mi video"
    assert "source" in session.last_call["files"]


def test_publish_raises_on_missing_video(tmp_path: Path) -> None:
    publisher = FacebookPagePublisher("123", "token", session=_FakeSession(_FakeResponse(200)))
    with pytest.raises(RuntimeError, match="No existe"):
        publisher.publish(tmp_path / "missing.mp4", title="", description="")


def test_publish_raises_when_not_configured(tmp_path: Path) -> None:
    video = tmp_path / "final.mp4"
    video.write_bytes(b"x")
    publisher = FacebookPagePublisher(None, None)
    with pytest.raises(RuntimeError, match="Falta NARR_FACEBOOK"):
        publisher.publish(video, title="", description="")


def test_publish_raises_with_api_error_message(tmp_path: Path) -> None:
    video = tmp_path / "final.mp4"
    video.write_bytes(b"x")
    session = _FakeSession(
        _FakeResponse(400, {"error": {"message": "Invalid OAuth access token."}})
    )
    publisher = FacebookPagePublisher("123", "bad-token", session=session)

    with pytest.raises(RuntimeError, match="Invalid OAuth access token"):
        publisher.publish(video, title="", description="")
