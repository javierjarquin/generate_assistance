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


def shots_for_duration(duration_seconds: float) -> int:
    """Número de tomas para que ninguna dure más de MAX_SHOT_SECONDS."""
    if duration_seconds <= 0:
        return 1
    needed = math.ceil(duration_seconds / MAX_SHOT_SECONDS)
    return max(1, min(needed, MAX_SHOTS_PER_PLANO))


def plan_shots(plano: Plano, render_duration: float) -> list[Shot]:
    total = shots_for_duration(render_duration)
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
