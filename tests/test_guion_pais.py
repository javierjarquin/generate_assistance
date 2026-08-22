"""El país declarado en el guion (meta.pais, con override por plano en
visual.pais) -- usado por ResearchPlanoMedia como fallback de búsqueda
más amplio cuando no aparece nada relevante (ver media_relevance.py)."""

import json

from illustrated_narrator.domain.services.script_loader import load_guion


def _write(tmp_path, data):
    p = tmp_path / "guion.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def _base(**plano_extra):
    plano = {"id": "p01", "narracion": "hola", "visual": {"tipo": "imagen_ia"}}
    plano.update(plano_extra)
    return {"meta": {"titulo": "t"}, "planos": [plano]}


def test_meta_pais_se_parsea(tmp_path):
    data = _base()
    data["meta"]["pais"] = "México"
    g = load_guion(_write(tmp_path, data))
    assert g.meta.pais == "México"


def test_sin_meta_pais_queda_none(tmp_path):
    g = load_guion(_write(tmp_path, _base()))
    assert g.meta.pais is None


def test_pais_por_plano_se_parsea(tmp_path):
    data = _base(visual={"tipo": "imagen_ia", "pais": "Estados Unidos"})
    g = load_guion(_write(tmp_path, data))
    assert g.planos[0].visual.pais == "Estados Unidos"


def test_plano_sin_pais_queda_none(tmp_path):
    g = load_guion(_write(tmp_path, _base()))
    assert g.planos[0].visual.pais is None
