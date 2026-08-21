from pathlib import Path

import requests

from illustrated_narrator.adapters.media.nasa_images_adapter import NasaImagesAdapter


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

    def get(self, url, params=None, headers=None, timeout=None):
        if "search" in url:
            return _FakeResponse(json_data=self._search_json)
        return _FakeResponse(content=b"fake-jpg-bytes")


_SEARCH_RESPONSE = {
    "collection": {
        "items": [
            {
                "data": [{"title": "Apollo 11", "nasa_id": "as11-40-5875", "photographer": "Neil Armstrong"}],
                "links": [{"href": "https://images-assets.nasa.gov/preview.jpg", "rel": "preview"}],
            },
            {
                "data": [{"title": "Sin preview", "nasa_id": "no-preview"}],
                "links": [{"href": "https://images-assets.nasa.gov/orig.jpg", "rel": "orig"}],
            },
        ]
    }
}


def test_search_descarga_solo_items_con_preview(tmp_path: Path) -> None:
    adapter = NasaImagesAdapter(session=_FakeSession(_SEARCH_RESPONSE))
    resultado = adapter.search("apollo", tmp_path, count=5)

    assert len(resultado) == 1
    candidate = resultado[0]
    assert candidate.title == "Apollo 11"
    assert candidate.source == "nasa"
    assert candidate.author == "Neil Armstrong"
    assert "dominio público" in candidate.license.lower() or "público" in candidate.license.lower()
    assert candidate.path.exists()
    assert candidate.path.read_bytes() == b"fake-jpg-bytes"


def test_sin_query_devuelve_vacio(tmp_path: Path) -> None:
    adapter = NasaImagesAdapter(session=_FakeSession(_SEARCH_RESPONSE))
    assert adapter.search("   ", tmp_path, count=3) == []


def test_busqueda_fallida_devuelve_vacio(tmp_path: Path) -> None:
    class _BrokenSession:
        def get(self, *a, **k):
            raise requests.exceptions.ConnectionError("red caída")

    adapter = NasaImagesAdapter(session=_BrokenSession())
    assert adapter.search("apollo", tmp_path, count=3) == []
