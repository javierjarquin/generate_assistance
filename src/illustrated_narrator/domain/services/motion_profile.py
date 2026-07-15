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
    # Segundos de vida media de la sacudida (None = constante todo el plano).
    # Un plano puede durar 20s+ (narración larga); sin decaimiento, "impact"
    # tiembla el clip entero, lo que se siente artificial — un temblor real
    # (terremoto, impacto) pega fuerte y se asienta en 1-2s, aunque la
    # cámara/narración sobre esa escena siga varios segundos más.
    shake_decay_seconds: float | None = None


_PROFILES = {
    "calm": MotionProfile("calm", zoom_per_frame=0.0006, max_zoom=1.18, shake_px=0, punch_in=0.0),
    "normal": MotionProfile("normal", zoom_per_frame=0.0016, max_zoom=1.30, shake_px=0, punch_in=0.03),
    "energetic": MotionProfile(
        "energetic", zoom_per_frame=0.0038, max_zoom=1.45, shake_px=4, punch_in=0.05,
        shake_decay_seconds=None,  # inquietud sostenida (persecución/acción): no se apaga
    ),
    "impact": MotionProfile(
        "impact", zoom_per_frame=0.0075, max_zoom=1.60, shake_px=13, punch_in=0.08,
        shake_decay_seconds=1.1,  # golpe fuerte que se asienta rápido
    ),
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


def resolve_motion(plano: Plano, min_level: str | None = None) -> MotionProfile:
    """Perfil de movimiento del plano: explícito o inferido.

    `min_level` es un piso que solo se aplica a perfiles INFERIDOS (p.ej. el
    tramo final del video no debe perder energía) — un `visual.motion`
    explícito del autor sigue ganando siempre, sin piso.
    """
    explicit = getattr(plano.visual, "motion", None)
    if explicit and explicit in _PROFILES:
        return _PROFILES[explicit]

    if plano.visual.shake:
        inferred = _PROFILES["impact"]
    else:
        text = f"{plano.narracion} {plano.visual.descripcion}".lower()
        if any(w in text for w in _IMPACT_WORDS):
            inferred = _PROFILES["impact"]
        elif plano.visual.overlay in ("fuego", "fire", "llamas"):
            inferred = _PROFILES["energetic"]
        elif any(w in text for w in _ENERGETIC_WORDS):
            inferred = _PROFILES["energetic"]
        else:
            inferred = _PROFILES["normal"]

    if min_level and MOTION_LEVELS.index(inferred.name) < MOTION_LEVELS.index(min_level):
        return _PROFILES[min_level]
    return inferred


def profile_by_name(name: str) -> MotionProfile:
    return _PROFILES.get(name, _PROFILES["normal"])
