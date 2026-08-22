"""continente_de / broaden_query -- el fallback geográfico de
research_plano_media.py (país -> continente, sin perder el contenido de
la query original)."""

from illustrated_narrator.domain.services.media_relevance import broaden_query, continente_de


def test_continente_de_pais_conocido():
    assert continente_de("México") == "North America"
    assert continente_de("mexico") == "North America"  # sin acento, case-insensitive
    assert continente_de("Argentina") == "South America"


def test_continente_de_pais_desconocido_devuelve_none():
    assert continente_de("Narnia") is None


def test_continente_de_sin_pais_devuelve_none():
    assert continente_de(None) is None
    assert continente_de("") is None


def test_broaden_query_agrega_el_ambito():
    assert broaden_query("prison cell block", "Mexico") == "prison cell block Mexico"


def test_broaden_query_sin_ambito_devuelve_none():
    assert broaden_query("prison cell block", None) is None
    assert broaden_query("prison cell block", "") is None


def test_broaden_query_no_duplica_si_ya_esta_incluido():
    assert broaden_query("prison cell block Mexico", "Mexico") is None
