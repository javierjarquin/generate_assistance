"""Taxonomía de SFX: palabra clave en audio.sfx del guion -> categoría de
sonido. Compartida entre el generador procedural (adapters/audio/audio_bed.py)
y la investigación de audio real (research_audio_assets.py) para que ambos
entiendan el mismo vocabulario sin duplicarlo.
"""

SFX_KEYWORDS = {
    "ola": "waves", "mar": "waves", "agua": "waves", "puerto": "waves",
    "fuego": "fire", "llama": "fire", "hoguera": "fire", "crepit": "fire",
    "terremoto": "rumble", "retumb": "rumble", "derrumb": "rumble", "temblor": "rumble",
    "viento": "wind", "niebla": "wind", "brisa": "wind",
    "burbuja": "bubbles", "submarino": "bubbles", "buceo": "bubbles",
}


def sfx_kind(sfx_text: str) -> str | None:
    lowered = sfx_text.lower()
    for keyword, kind in SFX_KEYWORDS.items():
        if keyword in lowered:
            return kind
    return None
