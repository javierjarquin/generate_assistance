import json

from illustrated_narrator.domain.services.script_loader import load_guion



def test_titulo_en_la_raiz_se_lee_igual_que_dentro_de_meta(tmp_path):
    # Los guiones de Dato Mata Gato traen `titulo` en la raíz y sin objeto
    # `meta`. Leer solo raw["meta"] dejaba el título vacío, y `narrator
    # publish` terminaba publicando en Facebook sin descripción.
    path = tmp_path / "guion.json"
    path.write_text(
        json.dumps(
            {
                "titulo": "El Estado no las buscó.",
                "planos": [
                    {
                        "id": "p00",
                        "narracion": "hola",
                        "visual": {"tipo": "imagen_ia"},
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    guion = load_guion(path)

    assert guion.meta.titulo == "El Estado no las buscó."


def test_meta_explicito_gana_sobre_la_raiz(tmp_path):
    path = tmp_path / "guion.json"
    path.write_text(
        json.dumps(
            {
                "titulo": "el de la raiz",
                "meta": {"titulo": "el de meta"},
                "planos": [
                    {
                        "id": "p00",
                        "narracion": "hola",
                        "visual": {"tipo": "imagen_ia"},
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    assert load_guion(path).meta.titulo == "el de meta"
