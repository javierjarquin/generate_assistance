from pathlib import Path

from illustrated_narrator.adapters.media.wikipedia_article_adapter import WikipediaArticleAdapter


class _FakeJsonResponse:
    def __init__(self, json_data: dict) -> None:
        self._json_data = json_data

    def raise_for_status(self) -> None:
        pass

    def json(self):
        return self._json_data


class _FakeStreamResponse:
    def __init__(self, content: bytes, content_length: str | None = None) -> None:
        self._content = content
        self.headers = {"Content-Length": content_length} if content_length else {}

    def raise_for_status(self) -> None:
        pass

    def iter_content(self, chunk_size: int):
        yield self._content

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _FakeCookieJar:
    def clear(self) -> None:
        pass


class _FakeSession:
    def __init__(self, search_json=None, images_json=None, imageinfo_json=None, image_bytes=b"fake-jpg") -> None:
        self.headers: dict = {}
        self.cookies = _FakeCookieJar()
        self._search_json = search_json
        self._images_json = images_json
        self._imageinfo_json = imageinfo_json
        self._image_bytes = image_bytes
        self.requested = []

    def mount(self, prefix, adapter) -> None:
        pass

    def get(self, url, params=None, timeout=None, stream=False, headers=None):
        self.requested.append(params or {})
        if stream:
            return _FakeStreamResponse(self._image_bytes)
        if params.get("list") == "search":
            return _FakeJsonResponse(self._search_json)
        if params.get("prop") == "images":
            return _FakeJsonResponse(self._images_json)
        if params.get("prop") == "imageinfo":
            return _FakeJsonResponse(self._imageinfo_json)
        raise AssertionError(f"llamada inesperada: {params}")


def test_sin_articulo_devuelve_vacio(tmp_path: Path) -> None:
    session = _FakeSession(search_json={"query": {"search": []}})
    adapter = WikipediaArticleAdapter(session=session)
    assert adapter.search("algo inexistente", tmp_path, count=3) == []


def test_search_encuentra_articulo_y_descarga_imagenes_de_contenido(tmp_path: Path) -> None:
    session = _FakeSession(
        search_json={"query": {"search": [{"title": "Criptografía"}]}},
        images_json={"query": {"pages": {"1": {"images": [
            {"title": "Archivo:Commons-logo.svg"},
            {"title": "Archivo:Maquina Enigma.jpg"},
        ]}}}},
        imageinfo_json={"query": {"pages": {"1": {
            "title": "Archivo:Maquina Enigma.jpg",
            "imagerepository": "shared",
            "imageinfo": [{"url": "https://example.com/enigma.jpg", "extmetadata": {
                "LicenseShortName": {"value": "CC BY-SA 4.0"},
                "Artist": {"value": "Alguien"},
            }}],
        }}}},
    )
    adapter = WikipediaArticleAdapter(session=session)

    resultado = adapter.search("criptografia", tmp_path, count=3)

    assert len(resultado) == 1
    assert resultado[0].title == "Archivo:Maquina Enigma.jpg"
    assert resultado[0].source == "wikipedia_articulo"
    assert resultado[0].license == "CC BY-SA 4.0"
    assert resultado[0].path.exists()


def test_descarta_imagenes_no_alojadas_en_commons(tmp_path: Path) -> None:
    session = _FakeSession(
        search_json={"query": {"search": [{"title": "Prueba"}]}},
        images_json={"query": {"pages": {"1": {"images": [{"title": "Archivo:Local.jpg"}]}}}},
        imageinfo_json={"query": {"pages": {"1": {
            "title": "Archivo:Local.jpg",
            "imagerepository": "local",
            "imageinfo": [{"url": "https://example.com/local.jpg", "extmetadata": {}}],
        }}}},
    )
    adapter = WikipediaArticleAdapter(session=session)
    assert adapter.search("prueba", tmp_path, count=3) == []


def test_sin_query_devuelve_vacio_sin_llamar_red(tmp_path: Path) -> None:
    session = _FakeSession()
    adapter = WikipediaArticleAdapter(session=session)
    assert adapter.search("   ", tmp_path, count=3) == []
    assert session.requested == []
