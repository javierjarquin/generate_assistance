"""Variante de Ken Burns por plano: determinista (mismo id -> misma variante
en cada corrida) para que un re-render no cambie el resultado al azar.
"""

_VARIANTS = (
    "zoom-in-center",
    "zoom-in-top-right",
    "zoom-in-bottom-left",
    "zoom-out-center",
    "pan-right",
    "pan-left",
)


def pan_direction_for(plano_id: str) -> str:
    index = sum(ord(c) for c in plano_id) % len(_VARIANTS)
    return _VARIANTS[index]
