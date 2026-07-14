from illustrated_narrator.domain.entities.plano import Plano, VisualSpec, VisualTipo
from illustrated_narrator.domain.services.motion_profile import resolve_motion


def _plano(narr="algo tranquilo", desc="", overlay=None, shake=False, motion=None) -> Plano:
    return Plano(
        id="p", seccion="s", narracion=narr,
        visual=VisualSpec(
            tipo=VisualTipo.IMAGEN_IA, prompt_ia="x", descripcion=desc,
            overlay=overlay, shake=shake, motion=motion,
        ),
    )


def test_explicit_motion_wins() -> None:
    assert resolve_motion(_plano(motion="impact")).name == "impact"
    assert resolve_motion(_plano(narr="terremoto brutal", motion="calm")).name == "calm"


def test_shake_flag_gives_impact() -> None:
    assert resolve_motion(_plano(shake=True)).name == "impact"


def test_impact_words_infer_impact() -> None:
    assert resolve_motion(_plano(narr="el meteorito explota contra la tierra")).name == "impact"
    assert resolve_motion(_plano(narr="todo se derrumba")).name == "impact"


def test_energetic_from_fire_overlay_or_words() -> None:
    assert resolve_motion(_plano(overlay="fuego")).name == "energetic"
    assert resolve_motion(_plano(narr="corren para escapar")).name == "energetic"


def test_calm_default_is_normal() -> None:
    assert resolve_motion(_plano(narr="una tarde tranquila junto al lago")).name == "normal"


def test_impact_moves_faster_than_calm() -> None:
    impact = resolve_motion(_plano(motion="impact"))
    calm = resolve_motion(_plano(motion="calm"))
    assert impact.zoom_per_frame > calm.zoom_per_frame
    assert impact.shake_px > 0 and calm.shake_px == 0
