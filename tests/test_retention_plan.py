from illustrated_narrator.domain.entities.plano import Plano, VisualSpec, VisualTipo
from illustrated_narrator.domain.services.retention_plan import (
    MAX_SHOT_SECONDS,
    plan_shots,
    shots_for_duration,
    variation_suffix,
)


def _plano(id_: str) -> Plano:
    return Plano(id=id_, seccion="s", narracion="x",
                 visual=VisualSpec(tipo=VisualTipo.IMAGEN_IA, prompt_ia="p"))


def test_short_plano_one_shot() -> None:
    assert shots_for_duration(3.0) == 1
    assert shots_for_duration(MAX_SHOT_SECONDS) == 1


def test_long_plano_splits() -> None:
    assert shots_for_duration(5.0) == 2   # >4s -> 2 tomas
    assert shots_for_duration(8.0) == 2
    assert shots_for_duration(9.0) == 3   # >8s -> 3 tomas


def test_shots_capped_at_three() -> None:
    assert shots_for_duration(60.0) == 3


def test_plan_shots_ids_and_flags() -> None:
    shots = plan_shots(_plano("p1"), render_duration=9.0)
    assert [s.shot_id for s in shots] == ["p1_1", "p1_2", "p1_3"]
    assert shots[0].is_extra is False
    assert shots[1].is_extra is True


def test_single_shot_keeps_plain_id() -> None:
    shots = plan_shots(_plano("p1"), render_duration=3.0)
    assert len(shots) == 1
    assert shots[0].shot_id == "p1"  # sin sufijo cuando es toma única


def test_variation_suffix_differs_for_extras() -> None:
    shots = plan_shots(_plano("p1"), render_duration=9.0)
    assert variation_suffix(shots[0]) == ""
    assert variation_suffix(shots[1]) != ""
    assert variation_suffix(shots[2]) != variation_suffix(shots[1])
