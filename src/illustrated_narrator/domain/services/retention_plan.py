"""Estándares de retención de la herramienta — reglas automáticas para CUALQUIER
guion, no ajustes de un video puntual.

La regla dura del formato corto: cambio visual cada pocos segundos. Un plano
largo con una sola imagen (aunque tenga Ken Burns) se siente estático y el
usuario hace scroll. Aquí se decide, sin intervención del autor:

- Cuántas "tomas" (imágenes distintas) merece cada plano según su duración,
  para que ninguna imagen quede en pantalla más de `max_shot_seconds`.
- Los sub-tiempos de corte dentro del plano.

El resto de estándares (loudnorm, CTA, título con caja, transiciones cortas)
viven en el ensamblador porque son de render, no de estructura.
"""

import math
from dataclasses import dataclass

from illustrated_narrator.domain.entities.plano import Plano

MAX_SHOT_SECONDS = 4.0  # ninguna imagen fija más de esto en pantalla
MAX_SHOTS_PER_PLANO = 3  # techo: generar más imágenes cuesta GPU

# Escalada de ritmo: un video con cortes parejos de principio a fin se siente
# plano hacia el clímax. A partir de _RAMP_START_FRACTION del tiempo total, el
# límite de segundos por toma baja gradualmente hasta _MIN_SHOT_SECONDS -> más
# cortes en el tramo final, sin tocar la duración real de cada plano (esa la
# fija la sincronía con el audio en render_timeline.py).
_RAMP_START_FRACTION = 0.75
_MIN_SHOT_SECONDS = 2.25

# Piso de intensidad de movimiento en el tramo final: aunque el contenido de
# un plano se infiera "calm", el video no debe perder energía justo antes del
# cierre.
_FINAL_STRETCH_FRACTION = 0.85
_FINAL_STRETCH_MIN_MOTION = "normal"


@dataclass(frozen=True)
class Shot:
    """Una toma dentro de un plano: su índice y la variación de prompt/seed."""

    plano_id: str
    index: int  # 0-based dentro del plano
    total: int  # tomas del plano

    @property
    def shot_id(self) -> str:
        return self.plano_id if self.total == 1 else f"{self.plano_id}_{self.index + 1}"

    @property
    def is_extra(self) -> bool:
        return self.index > 0


def shots_for_duration(duration_seconds: float, max_shot_seconds: float = MAX_SHOT_SECONDS) -> int:
    """Número de tomas para que ninguna dure más de `max_shot_seconds`."""
    if duration_seconds <= 0:
        return 1
    needed = math.ceil(duration_seconds / max_shot_seconds)
    return max(1, min(needed, MAX_SHOTS_PER_PLANO))


def max_shot_seconds_for_progress(progress: float) -> float:
    """Límite efectivo de segundos por toma según el progreso (0.0-1.0) del
    plano en el video total: constante hasta _RAMP_START_FRACTION, luego
    interpola linealmente hacia _MIN_SHOT_SECONDS -> más cortes según se
    acerca el clímax final."""
    progress = max(0.0, min(1.0, progress))
    if progress <= _RAMP_START_FRACTION:
        return MAX_SHOT_SECONDS
    t = (progress - _RAMP_START_FRACTION) / (1 - _RAMP_START_FRACTION)
    return MAX_SHOT_SECONDS - t * (MAX_SHOT_SECONDS - _MIN_SHOT_SECONDS)


def progress_map(planos_in_order: list[Plano], render_durations: dict[str, float]) -> dict[str, float]:
    """Progreso 0.0-1.0 de cada plano: fracción del tiempo total de video ya
    transcurrida ANTES de que empiece ese plano (por tiempo real, no por
    índice — más fiel a "hacia el final" cuando las duraciones son dispares)."""
    total = sum(render_durations[p.id] for p in planos_in_order)
    progress: dict[str, float] = {}
    elapsed = 0.0
    for p in planos_in_order:
        progress[p.id] = elapsed / total if total > 0 else 0.0
        elapsed += render_durations[p.id]
    return progress


def motion_floor_for_progress(progress: float) -> str | None:
    """Piso de intensidad de movimiento en el tramo final del video, o None
    si todavía no aplica ninguno."""
    return _FINAL_STRETCH_MIN_MOTION if progress >= _FINAL_STRETCH_FRACTION else None


def plan_shots(plano: Plano, render_duration: float, progress: float = 0.0) -> list[Shot]:
    total = shots_for_duration(render_duration, max_shot_seconds_for_progress(progress))
    return [Shot(plano_id=plano.id, index=i, total=total) for i in range(total)]


# Variaciones de encuadre para las tomas extra de un mismo plano: mismo tema,
# distinto ángulo -> el corte seco aporta dinamismo sin cambiar la narración.
_SHOT_VARIATIONS = (
    "",  # toma 1: prompt tal cual
    ", dramatic close-up detail, different angle",
    ", wide dramatic angle, different composition",
)


def variation_suffix(shot: Shot) -> str:
    return _SHOT_VARIATIONS[min(shot.index, len(_SHOT_VARIATIONS) - 1)]
