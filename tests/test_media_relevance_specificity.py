"""title_specificity -- desempate de relevance_score cuando varios
candidatos empatan (frecuente con nombres propios de 2 palabras: cualquier
título que las mencione da 1.0, sin importar cuántas palabras más tenga)."""

from illustrated_narrator.domain.services.media_relevance import relevance_score, title_specificity


def test_titulo_largo_y_titulo_corto_empatan_en_relevance_score():
    query = "Felipe Calderón"
    corto = "File:Felipe Calderón.jpg"
    largo = (
        "File:Brigadas Querétaro - Protesta contra reforma energética "
        "de Felipe Calderón - CDMX 2008.jpg"
    )
    assert relevance_score(query, corto) == 1.0
    assert relevance_score(query, largo) == 1.0


def test_title_specificity_prefiere_titulo_mas_corto():
    corto = "File:Felipe Calderón.jpg"
    largo = (
        "File:Brigadas Querétaro - Protesta contra reforma energética "
        "de Felipe Calderón - CDMX 2008.jpg"
    )
    assert title_specificity(corto) < title_specificity(largo)


def test_title_specificity_ignora_el_wrapper_file_y_extension():
    """Sin sacar "File:"/".jpg" antes de contar, un retrato real de
    Wikimedia pierde contra un título más corto de otra fuente (Openverse,
    sin ese wrapper) aunque el contenido sea peor -- confirmado en una
    corrida real: una caricatura de Felipe Calderón le ganó a su retrato
    real solo porque "File:Felipe Calderón.jpg" cuenta "file" y "jpg" como
    palabras."""
    retrato_wikimedia = "File:Felipe Calderón.jpg"
    caricatura_openverse = "Felipe Calderón - Caricature"
    assert title_specificity(retrato_wikimedia) < title_specificity(caricatura_openverse)
