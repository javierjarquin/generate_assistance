"""Cuenta regresiva durante el silencio posterior a una pregunta.

Un silencio a secas no se lee como "pensá la respuesta", se lee como que el
video se colgó (feedback real sobre el formato de trivia).
"""

from illustrated_narrator.adapters.video.ass_writer import _cuenta_regresiva
from illustrated_narrator.domain.entities.plano import Plano, VisualSpec, VisualTipo


def _plano(inicio: float, fin: float) -> Plano:
    p = Plano(
        id="p01",
        seccion="pregunta",
        narracion="¿Cuál es el río más largo?",
        visual=VisualSpec(tipo=VisualTipo.IMAGEN_IA, descripcion="", prompt_ia=""),
    )
    p.inicio_real_seg = inicio
    p.fin_real_seg = fin
    return p


def _numeros(eventos: list[str]) -> list[str]:
    return [e.rsplit("}", 1)[1].strip() for e in eventos]


def test_cuenta_hacia_atras_y_termina_con_la_respuesta():
    eventos = _cuenta_regresiva(_plano(10.0, 12.0), {"p01": 15.5}, 0.0)

    assert _numeros(eventos) == ["3", "2", "1"]
    # El último número se apaga justo cuando entra el plano de la respuesta.
    assert "0:00:15.50" in eventos[-1]


def test_pausa_de_respiracion_normal_no_dispara_contador():
    # Entre planos siempre hay décimas de silencio; ahí no va contador.
    assert _cuenta_regresiva(_plano(10.0, 12.0), {"p01": 12.4}, 0.0) == []


def test_sin_plano_siguiente_no_hay_contador():
    assert _cuenta_regresiva(_plano(10.0, 12.0), {}, 0.0) == []


def test_pausa_muy_larga_se_acota():
    # Una pausa enorme no debe llenar la pantalla de números.
    eventos = _cuenta_regresiva(_plano(0.0, 2.0), {"p01": 40.0}, 0.0)
    assert _numeros(eventos) == ["5", "4", "3", "2", "1"]


def test_respeta_el_desfase_de_la_tarjeta_de_intro():
    # time_offset_seconds corre todo el subtitulado cuando hay intro de marca.
    con_offset = _cuenta_regresiva(_plano(10.0, 12.0), {"p01": 15.5}, 2.0)
    assert "0:00:14.50" in con_offset[0]
