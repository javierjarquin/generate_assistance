import pytest

from illustrated_narrator.domain.entities.plano import Plano, VisualSpec, VisualTipo
from illustrated_narrator.domain.services.retention_plan import (
    MAX_SHOT_SECONDS,
    max_shot_seconds_for_progress,
    motion_floor_for_progress,
    plan_shots,
    progress_map,
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


def test_shots_capped_at_five() -> None:
    assert shots_for_duration(60.0) == 5


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


def test_max_shot_seconds_constant_before_ramp() -> None:
    assert max_shot_seconds_for_progress(0.0) == MAX_SHOT_SECONDS
    assert max_shot_seconds_for_progress(0.75) == MAX_SHOT_SECONDS


def test_max_shot_seconds_shrinks_toward_climax() -> None:
    assert max_shot_seconds_for_progress(1.0) < MAX_SHOT_SECONDS
    # monótona no creciente
    prev = max_shot_seconds_for_progress(0.75)
    for p in (0.8, 0.9, 1.0):
        cur = max_shot_seconds_for_progress(p)
        assert cur <= prev
        prev = cur


def test_plan_shots_more_cuts_near_climax() -> None:
    # 3.5s: con el límite base (4.0s) entra en 1 toma; cerca del clímax
    # (progreso 1.0, límite ~2.25s) debe partirse en más tomas.
    early = plan_shots(_plano("p1"), render_duration=3.5, progress=0.0)
    late = plan_shots(_plano("p1"), render_duration=3.5, progress=1.0)
    assert len(early) == 1
    assert len(late) > len(early)


def test_progress_map_first_plano_is_zero_and_increases() -> None:
    planos = [_plano("p1"), _plano("p2"), _plano("p3")]
    durations = {"p1": 10.0, "p2": 10.0, "p3": 10.0}
    progress = progress_map(planos, durations)
    assert progress["p1"] == 0.0
    assert progress["p2"] == pytest.approx(1 / 3)
    assert progress["p3"] == pytest.approx(2 / 3)


def test_motion_floor_only_applies_near_the_end() -> None:
    assert motion_floor_for_progress(0.5) is None
    assert motion_floor_for_progress(0.9) == "normal"
