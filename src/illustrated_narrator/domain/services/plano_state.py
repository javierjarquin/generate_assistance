"""Persistencia del estado de los planos (planos_alineados.json): la bitacora
que permite reanudar una corrida sin repetir transcripcion/alineacion/imagenes
ya hechas. Ver plan: resumibilidad por diseño.
"""

import json
from pathlib import Path

from illustrated_narrator.domain.entities.plano import Plano, PlanoEstado


def save_planos_state(planos: list[Plano], path: Path) -> None:
    data = [
        {
            "id": p.id,
            "inicio_real_seg": p.inicio_real_seg,
            "fin_real_seg": p.fin_real_seg,
            "estado": p.estado.value,
            "imagen_path": p.imagen_path,
            "clip_path": p.clip_path,
        }
        for p in planos
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def load_planos_state(planos: list[Plano], path: Path) -> None:
    """Aplica el estado guardado a los planos (mutación in-place, por id)."""
    if not path.exists():
        return
    saved = {row["id"]: row for row in json.loads(path.read_text(encoding="utf-8"))}
    for plano in planos:
        row = saved.get(plano.id)
        if not row:
            continue
        plano.inicio_real_seg = row["inicio_real_seg"]
        plano.fin_real_seg = row["fin_real_seg"]
        plano.estado = PlanoEstado(row["estado"])
        plano.imagen_path = row["imagen_path"]
        plano.clip_path = row["clip_path"]
