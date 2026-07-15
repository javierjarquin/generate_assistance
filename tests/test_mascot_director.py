from illustrated_narrator.domain.services.mascot_director import (
    CELEBRATE,
    IDLE,
    JUMP,
    POINT,
    SAD,
    SCARED,
    SURPRISED,
    TALK,
    THINK,
    WALK,
    WAVE,
    MascotSegment,
    PlanoBeat,
    action_at,
    infer_expression,
    plan_mascot,
    segment_at,
)

_ALL = {TALK, IDLE, WAVE, WALK, POINT, JUMP, CELEBRATE, SCARED, SURPRISED, THINK, SAD, "laugh"}


def test_first_plano_waves_then_talks() -> None:
    beats = [PlanoBeat(0.0, 6.0, energetic=False)]
    segs = plan_mascot(beats, available={TALK, IDLE, WAVE})
    assert segs[0].action == WAVE
    assert segs[0].start == 0.0
    assert segs[1].action == TALK
    assert segs[1].end == 6.0


def test_energetic_plano_jumps_if_available() -> None:
    beats = [PlanoBeat(0.0, 3.0, False), PlanoBeat(3.0, 8.0, energetic=True)]
    segs = plan_mascot(beats, available={TALK, IDLE, JUMP, WAVE})
    jump = [s for s in segs if s.action == JUMP]
    assert jump and jump[0].start == 3.0


def test_missing_optional_falls_back_to_talk() -> None:
    beats = [PlanoBeat(0.0, 5.0, energetic=True)]
    segs = plan_mascot(beats, available={TALK, IDLE})  # sin jump/wave
    assert all(s.action in (TALK, IDLE) for s in segs)
    assert segs[0].action == TALK


def test_cta_celebrates() -> None:
    beats = [PlanoBeat(0.0, 5.0, False)]
    segs = plan_mascot(beats, available={TALK, IDLE, CELEBRATE}, cta_start=5.0, cta_duration=3.0)
    assert segs[-1] == MascotSegment(5.0, 8.0, CELEBRATE)


def test_action_at_returns_idle_outside_segments() -> None:
    segs = [MascotSegment(1.0, 2.0, TALK)]
    assert action_at(segs, 0.5) == IDLE
    assert action_at(segs, 1.5) == TALK
    assert action_at(segs, 2.5) == IDLE


def test_infer_expression_from_content() -> None:
    assert infer_expression("un terremoto destruyó la ciudad", False, _ALL) == SCARED
    assert infer_expression("nadie sabía el secreto que reveló", False, _ALL) == SURPRISED
    assert infer_expression("¿por qué pasó esto? un misterio", False, _ALL) == THINK
    assert infer_expression("murió en la tragedia", False, _ALL) == SAD
    assert infer_expression("medía 300 metros de alto, un récord", False, _ALL) == POINT
    assert infer_expression("una tarde normal cualquiera", False, _ALL) is None


def test_infer_falls_back_when_expression_missing() -> None:
    # sin 'scared' cae a 'think'; sin 'scared' ni 'think' cae a idle
    assert infer_expression("peligro, un monstruo", False, {TALK, IDLE, THINK}) == THINK
    assert infer_expression("peligro, un monstruo", False, {TALK, IDLE}) == IDLE


def test_energetic_without_keyword_jumps() -> None:
    assert infer_expression("y entonces avanzó", True, _ALL) == JUMP


def test_entrance_walks_in_then_waves() -> None:
    beats = [PlanoBeat(0.0, 8.0, energetic=False, text="hola a todos")]
    segs = plan_mascot(beats, available=_ALL)
    assert segs[0].action == WALK and segs[0].variant == "in" and segs[0].start == 0.0
    assert segs[1].action == WAVE
    assert segs[2].action == TALK


def test_content_drives_plano_expression() -> None:
    beats = [
        PlanoBeat(0.0, 4.0, False, "bienvenidos"),
        PlanoBeat(4.0, 9.0, False, "de repente todo cambió, increíble"),
    ]
    segs = plan_mascot(beats, available=_ALL)
    assert any(s.action == SURPRISED and s.start == 4.0 for s in segs)


def test_calm_even_plano_paces() -> None:
    beats = [
        PlanoBeat(0.0, 4.0, False, "hola"),
        PlanoBeat(4.0, 9.0, False, "seguia el relato"),
        PlanoBeat(9.0, 14.0, False, "seguia siendo un dia tranquilo"),  # i=2 (par)
    ]
    segs = plan_mascot(beats, available=_ALL)
    assert any(s.action == WALK and s.variant == "pace" and s.start == 9.0 for s in segs)


def test_segment_at() -> None:
    segs = [MascotSegment(1.0, 2.0, WALK, "in")]
    assert segment_at(segs, 1.5).variant == "in"
    assert segment_at(segs, 3.0) is None
