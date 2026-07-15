"""Dirección de la mascota: decide QUÉ acción hace en cada momento del video para
que se sienta que está presentando —no un muñeco pegado—.

Es lógica pura (no toca imágenes ni ffmpeg). Toma la línea de tiempo de los
planos y devuelve segmentos (inicio, fin, acción). El compositor luego dibuja
los sprites y, dentro de los segmentos de "hablar", alterna a "idle" cuando la
voz calla (lip-sync por presencia de voz).

Acciones (el usuario las provee como carpetas/animaciones; ver README):
- talk      : hablando (boca en movimiento) — base mientras narra un plano
- idle      : quieta, respira/parpadea — pausas y relleno
- wave      : saluda — entrada del contenido
- walk      : camina — entra a un plano nuevo (transición)
- point     : señala — énfasis / cada ciertos planos
- jump      : salta — planos de mucha energía (impacto)
- celebrate : festeja — cierre / CTA

Si una acción opcional no existe en la carpeta, se cae a `talk`/`idle`.
"""

from dataclasses import dataclass

TALK = "talk"
IDLE = "idle"
WAVE = "wave"
WALK = "walk"
POINT = "point"
JUMP = "jump"
CELEBRATE = "celebrate"

REQUIRED_ACTIONS = (TALK, IDLE)
OPTIONAL_ACTIONS = (WAVE, WALK, POINT, JUMP, CELEBRATE)
ALL_ACTIONS = REQUIRED_ACTIONS + OPTIONAL_ACTIONS

_ONESHOT_SECONDS = 0.9  # duración típica de un gesto puntual (wave/point/jump...)


@dataclass(frozen=True)
class PlanoBeat:
    """Lo que el director necesita de cada plano, ya con el offset de intro."""

    start: float
    end: float
    energetic: bool  # motion impact/energetic -> candidato a saltar


@dataclass(frozen=True)
class MascotSegment:
    start: float
    end: float
    action: str


def plan_mascot(
    beats: list[PlanoBeat],
    available: set[str],
    cta_start: float | None = None,
    cta_duration: float = 3.0,
) -> list[MascotSegment]:
    """Devuelve los segmentos de acción de la mascota, en orden y sin huecos
    dentro de cada plano (el compositor rellena el resto con idle)."""
    if not beats:
        return []
    segs: list[MascotSegment] = []

    def oneshot(start: float, end: float, action: str) -> float:
        """Coloca un gesto puntual al inicio del plano si la acción existe.
        Devuelve el tiempo donde sigue el 'talk'."""
        if action in available:
            gesture_end = min(start + _ONESHOT_SECONDS, end)
            segs.append(MascotSegment(start, gesture_end, action))
            return gesture_end
        return start

    for i, b in enumerate(beats):
        t = b.start
        if i == 0:
            t = oneshot(t, b.end, WAVE)          # saludo de entrada
        elif b.energetic:
            t = oneshot(t, b.end, JUMP)          # plano de energía -> salta
        elif i % 3 == 0:
            t = oneshot(t, b.end, POINT)         # cada 3 planos -> señala
        else:
            t = oneshot(t, b.end, WALK)          # entra caminando
        if t < b.end:
            segs.append(MascotSegment(t, b.end, TALK))

    # Cierre / CTA: festeja si se puede
    if cta_start is not None:
        segs.append(
            MascotSegment(cta_start, cta_start + cta_duration,
                          CELEBRATE if CELEBRATE in available else IDLE)
        )
    return segs


def action_at(segments: list[MascotSegment], t: float) -> str:
    """Acción activa en el instante t (idle si no hay segmento)."""
    for s in segments:
        if s.start <= t < s.end:
            return s.action
    return IDLE
