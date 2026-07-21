"""La mascota configurada desde el guion: meta.mascota (video) y
planos[].mascota.expresion (override por plano)."""

import json

import pytest

from illustrated_narrator.domain.services.mascot_director import (
    IDLE,
    SCARED,
    TALK,
    WAVE,
    PlanoBeat,
    plan_mascot,
)
from illustrated_narrator.domain.services.script_loader import GuionValidationError, load_guion

_ALL = {TALK, IDLE, WAVE, "walk", "point", "jump", "celebrate", SCARED, "surprised",
        "think", "sad", "laugh"}


def _write(tmp_path, data) -> "object":
    p = tmp_path / "guion.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def _base(**plano_extra):
    plano = {"id": "p01", "narracion": "hola", "visual": {"tipo": "imagen_ia"}}
    plano.update(plano_extra)
    return {"meta": {"titulo": "t"}, "planos": [plano]}


def test_meta_mascota_se_parsea(tmp_path):
    data = _base()
    data["meta"]["mascota"] = {
        "modo": "mascota", "ruta": "./mascota", "pos": "bottom-left",
        "alto": 0.4, "fps": 15, "umbral_voz": 0.08,
    }
    g = load_guion(_write(tmp_path, data))
    m = g.meta.mascota
    assert m.modo == "mascota" and m.ruta == "./mascota" and m.pos == "bottom-left"
    assert m.alto == 0.4 and m.fps == 15 and m.umbral_voz == 0.08


def test_sin_meta_mascota_queda_none(tmp_path):
    g = load_guion(_write(tmp_path, _base()))
    assert g.meta.mascota is None  # manda el entorno


def test_modo_invalido_falla(tmp_path):
    data = _base()
    data["meta"]["mascota"] = {"modo": "robot"}
    with pytest.raises(GuionValidationError, match="modo"):
        load_guion(_write(tmp_path, data))


def test_pos_invalida_falla(tmp_path):
    data = _base()
    data["meta"]["mascota"] = {"pos": "top-left"}
    with pytest.raises(GuionValidationError, match="pos"):
        load_guion(_write(tmp_path, data))


def test_expresion_por_plano_se_parsea(tmp_path):
    g = load_guion(_write(tmp_path, _base(mascota={"expresion": "scared"})))
    assert g.planos[0].mascota_expresion == "scared"


def test_expresion_invalida_falla(tmp_path):
    with pytest.raises(GuionValidationError, match="expresion"):
        load_guion(_write(tmp_path, _base(mascota={"expresion": "bailar"})))


def test_plano_sin_mascota_no_fuerza_expresion(tmp_path):
    g = load_guion(_write(tmp_path, _base()))
    assert g.planos[0].mascota_expresion is None


def test_override_gana_sobre_inferencia():
    # el texto no tiene palabras de peligro, pero el guion fuerza 'scared'
    beats = [
        PlanoBeat(0.0, 5.0, False, "hola"),
        PlanoBeat(5.0, 10.0, False, "una tarde tranquila", expresion=SCARED),
    ]
    segs = plan_mascot(beats, available=_ALL)
    assert any(s.action == SCARED for s in segs)


def test_override_gana_incluso_en_el_primer_plano():
    beats = [PlanoBeat(0.0, 8.0, False, "hola a todos", expresion="point")]
    segs = plan_mascot(beats, available=_ALL)
    assert any(s.action == "point" for s in segs)
    assert not any(s.action == WAVE for s in segs)  # el saludo cede al override


def test_override_cae_a_disponible_si_falta_el_sprite():
    # sin 'scared' en la carpeta, cae por la cadena (scared -> think -> idle)
    beats = [PlanoBeat(0.0, 5.0, False, "x", expresion=SCARED)]
    segs = plan_mascot(beats, available={TALK, IDLE, "think"})
    assert any(s.action == "think" for s in segs)
