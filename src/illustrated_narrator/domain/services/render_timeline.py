"""Duraciones de render por plano para mantener el video en sincronía con el audio.

El audio es continuo; entre plano y plano hay pausas de respiración que la
alineación deja fuera (fin de última palabra -> inicio de la siguiente). Si
cada clip durara solo lo hablado, el video quedaría más corto que el audio y
se desincronizaría acumulativamente — y cada crossfade además SOLAPA (resta)
xfade segundos.

Regla: el clip de un plano cubre desde su inicio real hasta el inicio real del
siguiente plano, MÁS la duración del crossfade (que el solape consume). Con
eso, la posición en video del inicio de cada plano coincide exactamente con su
timestamp en el audio. El primer clip arranca en 0 (cubre el silencio inicial)
y el último agrega una cola para cubrir el cierre del audio.
"""

from illustrated_narrator.domain.entities.plano import Plano


def compute_render_durations(
    planos_in_order: list[Plano],
    xfade_duration: float,
    tail_seconds: float = 1.5,
) -> dict[str, float]:
    """planos_in_order: alineados y renderizables, ordenados por inicio_real_seg."""
    durations: dict[str, float] = {}
    total = len(planos_in_order)
    for i, plano in enumerate(planos_in_order):
        start = 0.0 if i == 0 else float(plano.inicio_real_seg)
        if i < total - 1:
            end = float(planos_in_order[i + 1].inicio_real_seg) + xfade_duration
        else:
            end = float(plano.fin_real_seg) + tail_seconds
        durations[plano.id] = max(end - start, 0.5)
    return durations
