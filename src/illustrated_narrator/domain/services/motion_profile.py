"""Perfil de movimiento por contenido — el Ken Burns deja de ser uniforme.

El problema del video plano: todos los planos se mueven igual de lento, así un
impacto de meteorito y una roca en calma tienen la misma energía → se siente
soso. Aquí cada plano recibe una intensidad de movimiento según su contenido:

- impact:    zoom rápido + sacudida fuerte (impactos, terremotos, explosiones)
- energetic: zoom notable + leve inquietud (acción, tensión, persecución)
- normal:    Ken Burns estándar
- calm:      deriva lenta (paisajes, reflexión, cierres)

La intensidad se toma de `visual.motion` si el guion la fija; si no, se infiere
de señales del plano (shake, overlay, palabras de la narración).
"""

from dataclasses import dataclass

from illustrated_narrator.domain.entities.plano import Plano

MOTION_LEVELS = ("calm", "normal", "energetic", "impact")


@dataclass(frozen=True)
class MotionProfile:
    name: str
    zoom_per_frame: float  # velocidad de acercamiento por frame
    max_zoom: float        # tope del zoom
    shake_px: int          # amplitud de sacudida (0 = sin sacudida)
    punch_in: float        # escala extra al entrar (0.0 = sin punch-in)


_PROFILES = {
    "calm": MotionProfile("calm", zoom_per_frame=0.0006, max_zoom=1.18, shake_px=0, punch_in=0.0),
    "normal": MotionProfile("normal", zoom_per_frame=0.0016, max_zoom=1.30, shake_px=0, punch_in=0.03),
    "energetic": MotionProfile("energetic", zoom_per_frame=0.0038, max_zoom=1.45, shake_px=4, punch_in=0.05),
    "impact": MotionProfile("impact", zoom_per_frame=0.0075, max_zoom=1.60, shake_px=13, punch_in=0.08),
}

# Palabras en la narración que suben la energía del movimiento
_IMPACT_WORDS = (
    "impact", "explot", "explos", "meteor", "terremoto", "estall", "choque",
    "colis", "destru", "derrumb", "erupci", "catastr", "devast", "golpe",
    "onda expansiva", "estrell",
)
_ENERGETIC_WORDS = (
    "corr", "escap", "persec", "huy", "veloz", "rápid", "ataq", "caza",
    "pelea", "lucha", "tormenta", "fuego", "llama", "guerra", "caos",
)


def resolve_motion(plano: Plano) -> MotionProfile:
    """Perfil de movimiento del plano: explícito o inferido."""
    explicit = getattr(plano.visual, "motion", None)
    if explicit and explicit in _PROFILES:
        return _PROFILES[explicit]

    if plano.visual.shake:
        return _PROFILES["impact"]

    text = f"{plano.narracion} {plano.visual.descripcion}".lower()
    if any(w in text for w in _IMPACT_WORDS):
        return _PROFILES["impact"]
    if plano.visual.overlay in ("fuego", "fire", "llamas"):
        return _PROFILES["energetic"]
    if any(w in text for w in _ENERGETIC_WORDS):
        return _PROFILES["energetic"]
    return _PROFILES["normal"]


def profile_by_name(name: str) -> MotionProfile:
    return _PROFILES.get(name, _PROFILES["normal"])
