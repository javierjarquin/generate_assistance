from illustrated_narrator.adapters.video.ffmpeg_assembler import _shake_amplitude_expr


def test_no_decay_gives_constant_amplitude() -> None:
    assert _shake_amplitude_expr(13, None) == "13"


def test_decay_produces_exponential_expression() -> None:
    expr = _shake_amplitude_expr(13, 1.1)
    assert expr == "13*exp(-t/1.1)"


def test_zero_decay_seconds_treated_as_no_decay() -> None:
    # 0 es falsy -- evita dividir por cero en la expresión ffmpeg
    assert _shake_amplitude_expr(4, 0) == "4"
