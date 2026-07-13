from illustrated_narrator.domain.entities.plano import Plano, VisualSpec, VisualTipo
from illustrated_narrator.domain.services.render_timeline import compute_render_durations


def _plano(id_: str, start: float, end: float) -> Plano:
    p = Plano(
        id=id_, seccion="s", narracion="x",
        visual=VisualSpec(tipo=VisualTipo.IMAGEN_IA, prompt_ia="x"),
    )
    p.inicio_real_seg = start
    p.fin_real_seg = end
    return p


def test_gaps_between_planos_are_filled_and_xfade_compensated() -> None:
    # Hablado: p1 2-9s, p2 10.5-19s (pausa 1.5s), p3 20-28s (pausa 1s)
    planos = [_plano("p1", 2.0, 9.0), _plano("p2", 10.5, 19.0), _plano("p3", 20.0, 28.0)]

    durations = compute_render_durations(planos, xfade_duration=0.5, tail_seconds=1.5)

    # p1 cubre desde 0 (silencio inicial) hasta inicio de p2 + xfade
    assert durations["p1"] == 10.5 + 0.5
    # p2 cubre su inicio hasta inicio de p3 + xfade
    assert durations["p2"] == (20.0 - 10.5) + 0.5
    # último: hablado + cola
    assert durations["p3"] == (28.0 - 20.0) + 1.5

    # Propiedad clave: posición en video del inicio de cada plano == timestamp real.
    # offset_k = suma de (dur_i - xfade) para i < k
    offset_p2 = durations["p1"] - 0.5
    offset_p3 = offset_p2 + durations["p2"] - 0.5
    assert offset_p2 == 10.5
    assert offset_p3 == 20.0


def test_single_plano_covers_from_zero_plus_tail() -> None:
    durations = compute_render_durations([_plano("p1", 3.0, 12.0)], 0.5, tail_seconds=1.5)
    assert durations["p1"] == 12.0 + 1.5  # desde 0 hasta fin + cola


def test_duration_floor_prevents_degenerate_clips() -> None:
    planos = [_plano("p1", 0.0, 0.1), _plano("p2", 0.1, 5.0)]
    durations = compute_render_durations(planos, 0.5)
    assert all(d >= 0.5 for d in durations.values())
