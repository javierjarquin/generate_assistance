from pathlib import Path

from illustrated_narrator.adapters.media.pexels_video_adapter import (
    PexelsVideoAdapter,
    _pick_video_file,
    _slug_from_url,
)


class _FakeResponse:
    def __init__(self, json_data=None, content: bytes = b"") -> None:
        self._json_data = json_data
        self.content = content

    def raise_for_status(self) -> None:
        pass

    def json(self):
        return self._json_data


class _FakeSession:
    def __init__(self, search_json: dict) -> None:
        self._search_json = search_json
        self.requested_urls: list[str] = []

    def get(self, url: str, headers=None, params=None, timeout=None):
        self.requested_urls.append(url)
        if "videos/search" in url:
            return _FakeResponse(json_data=self._search_json)
        return _FakeResponse(content=b"fake-mp4-bytes")


_SEARCH_RESPONSE = {
    "videos": [
        {
            "id": 2499611,
            "duration": 12,
            "url": "https://www.pexels.com/video/aerial-footage-of-a-forest-2499611/",
            "user": {"name": "Jane Doe"},
            "video_files": [
                {"quality": "sd", "file_type": "video/mp4", "width": 640, "link": "https://x/sd.mp4"},
                {"quality": "hd", "file_type": "video/mp4", "width": 1920, "link": "https://x/hd.mp4"},
                {"quality": "hd", "file_type": "video/mp4", "width": 1280, "link": "https://x/hd720.mp4"},
            ],
        }
    ]
}


def test_is_available_requires_key() -> None:
    assert PexelsVideoAdapter(None).is_available() is False
    assert PexelsVideoAdapter("some-key").is_available() is True


def test_search_downloads_best_match(tmp_path: Path) -> None:
    session = _FakeSession(_SEARCH_RESPONSE)
    adapter = PexelsVideoAdapter("key", vertical=False, session=session)

    candidates = adapter.search("forest aerial", tmp_path, count=3)

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.media_type == "video"
    assert candidate.source == "pexels_video"
    assert candidate.author == "Jane Doe"
    assert candidate.path.exists()
    assert candidate.path.read_bytes() == b"fake-mp4-bytes"
    # eligió el hd más cercano a 1920 (target landscape), no el sd ni el hd720
    assert session.requested_urls[-1] == "https://x/hd.mp4"


def test_search_without_query_returns_empty(tmp_path: Path) -> None:
    adapter = PexelsVideoAdapter("key", session=_FakeSession(_SEARCH_RESPONSE))
    assert adapter.search("   ", tmp_path, count=3) == []


def test_pick_video_file_prefers_hd_closest_width() -> None:
    files = [
        {"quality": "sd", "file_type": "video/mp4", "width": 640, "link": "sd"},
        {"quality": "hd", "file_type": "video/mp4", "width": 1280, "link": "hd720"},
        {"quality": "hd", "file_type": "video/mp4", "width": 1920, "link": "hd1080"},
    ]
    chosen = _pick_video_file(files, target_w=1920)
    assert chosen["link"] == "hd1080"


def test_pick_video_file_falls_back_to_sd_without_hd() -> None:
    files = [{"quality": "sd", "file_type": "video/mp4", "width": 640, "link": "sd"}]
    chosen = _pick_video_file(files, target_w=1920)
    assert chosen["link"] == "sd"


def test_pick_video_file_ignores_non_mp4() -> None:
    files = [{"quality": "hd", "file_type": "video/webm", "width": 1920, "link": "webm"}]
    assert _pick_video_file(files, target_w=1920) is None


def test_slug_from_url_extracts_readable_text() -> None:
    url = "https://www.pexels.com/video/aerial-footage-of-a-forest-2499611/"
    assert _slug_from_url(url) == "aerial footage of a forest"


def test_slug_from_url_handles_garbage() -> None:
    assert _slug_from_url("") == ""
    assert _slug_from_url("https://example.com/not-a-pexels-url") == ""
