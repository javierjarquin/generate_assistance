from illustrated_narrator.domain.services.brand_palette import (
    DEFAULT_ACCENT_HEX,
    hex_to_ass_color,
    hex_to_ffmpeg_color,
)


def test_default_accent_matches_hardcoded_karaoke_yellow() -> None:
    # Debe reproducir exactamente el &H0000E8FF que ya tenía ass_writer.py
    # hardcodeado -- con la config por defecto nada cambia visualmente.
    assert hex_to_ass_color(DEFAULT_ACCENT_HEX) == "&H0000E8FF"


def test_default_accent_ffmpeg_format() -> None:
    assert hex_to_ffmpeg_color(DEFAULT_ACCENT_HEX) == "0xFFE800"


def test_hex_to_ass_color_reorders_to_bgr() -> None:
    assert hex_to_ass_color("#112233") == "&H00332211"


def test_hex_to_ffmpeg_color_keeps_rgb_order() -> None:
    assert hex_to_ffmpeg_color("#112233") == "0x112233"
