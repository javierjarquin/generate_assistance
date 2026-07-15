from illustrated_narrator.domain.services.mascot_director import (
    CELEBRATE,
    IDLE,
    JUMP,
    TALK,
    WAVE,
    MascotSegment,
    PlanoBeat,
    action_at,
    plan_mascot,
)


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
