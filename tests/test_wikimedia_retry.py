"""upload.wikimedia.org (la CDN de descarga, no la API de búsqueda) devuelve
403 -- no 429 -- cuando la carga total de la sesión es alta, aunque el
archivo exista y sea público (confirmado en una corrida real: 403 repetido
durante ~14 min para archivos reales de figuras públicas, mismo archivo
con curl aislado después dio 200 sin cambiar nada)."""

from illustrated_narrator.adapters.media.wikimedia_adapter import WikimediaCommonsAdapter


def test_wikimedia_reintenta_403():
    adapter = WikimediaCommonsAdapter()
    transport = adapter._http.get_adapter("https://commons.wikimedia.org/w/api.php")
    assert 403 in transport.max_retries.status_forcelist
    assert 429 in transport.max_retries.status_forcelist
