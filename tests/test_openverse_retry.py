"""Openverse agrega archivos alojados en la CDN de Wikimedia (upload.
wikimedia.org) sin pasar por su propia CDN -- esas descargas compiten con
las de WikimediaCommonsAdapter por el mismo host y, sin throttle propio,
aceleran el 403 por carga (ver wikimedia_adapter.py, mismo síntoma
confirmado en una corrida real)."""

from illustrated_narrator.adapters.media.openverse_adapter import OpenverseAdapter


def test_openverse_reintenta_403():
    adapter = OpenverseAdapter()
    transport = adapter._http.get_adapter("https://api.openverse.org/v1/images/")
    assert 403 in transport.max_retries.status_forcelist
    assert 429 in transport.max_retries.status_forcelist


def test_openverse_throttlea_descargas(monkeypatch):
    adapter = OpenverseAdapter()
    sleeps: list[float] = []
    monkeypatch.setattr(
        "illustrated_narrator.adapters.media.openverse_adapter.time.sleep",
        lambda s: sleeps.append(s),
    )
    adapter._throttle()
    adapter._throttle()
    assert sleeps  # la segunda llamada, inmediata después de la primera, debe esperar
