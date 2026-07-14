"""Carga un guion.json (formato planos[]) a las entidades del dominio.

No valida contra el _schema del archivo -- solo lee los campos que la
herramienta usa. Campos desconocidos/extra en el JSON (verificacion_datos,
notas_produccion, b_roll_a_conseguir, etc.) se ignoran aqui: son metadata de
produccion para humanos, no entrada del pipeline.
"""

import json
from pathlib import Path

from illustrated_narrator.domain.entities.guion import Guion, GuionMeta
from illustrated_narrator.domain.entities.plano import AudioSpec, Plano, VisualSpec, VisualTipo


class GuionValidationError(Exception):
    pass


def load_guion(path: Path) -> Guion:
    raw = json.loads(path.read_text(encoding="utf-8"))
    meta = _parse_meta(raw.get("meta", {}))
    planos_raw = raw.get("planos")
    if not planos_raw:
        raise GuionValidationError(f"{path}: sin 'planos[]' o esta vacio")

    planos = []
    seen_ids: set[str] = set()
    for i, p in enumerate(planos_raw):
        plano = _parse_plano(p, index=i)
        if plano.id in seen_ids:
            raise GuionValidationError(f"plano id duplicado: {plano.id}")
        seen_ids.add(plano.id)
        planos.append(plano)

    return Guion(meta=meta, planos=planos)


def _parse_meta(raw: dict) -> GuionMeta:
    return GuionMeta(
        serie=raw.get("serie", ""),
        capitulo=raw.get("capitulo", 0),
        titulo=raw.get("titulo", ""),
        subtitulo=raw.get("subtitulo"),
        idioma=raw.get("idioma", "es-MX"),
        gancho=raw.get("gancho"),
    )


def _parse_plano(raw: dict, index: int) -> Plano:
    if "id" not in raw:
        raise GuionValidationError(f"plano #{index}: falta 'id'")
    if "narracion" not in raw or not raw["narracion"].strip():
        raise GuionValidationError(f"plano {raw.get('id', index)}: falta 'narracion'")
    if "visual" not in raw or "tipo" not in raw["visual"]:
        raise GuionValidationError(f"plano {raw['id']}: falta 'visual.tipo'")

    visual_raw = raw["visual"]
    try:
        tipo = VisualTipo(visual_raw["tipo"])
    except ValueError as exc:
        valid = ", ".join(t.value for t in VisualTipo)
        raise GuionValidationError(
            f"plano {raw['id']}: visual.tipo '{visual_raw['tipo']}' invalido (opciones: {valid})"
        ) from exc

    visual = VisualSpec(
        tipo=tipo,
        descripcion=visual_raw.get("descripcion", ""),
        prompt_ia=visual_raw.get("prompt_ia", ""),
        nota=visual_raw.get("nota"),
        overlay=visual_raw.get("overlay"),
        shake=bool(visual_raw.get("shake", False)),
        motion=visual_raw.get("motion"),
        busqueda_medios=visual_raw.get("busqueda_medios"),
    )
    audio_raw = raw.get("audio", {})
    audio = AudioSpec(musica=audio_raw.get("musica"), sfx=audio_raw.get("sfx"))

    return Plano(
        id=raw["id"],
        seccion=raw.get("seccion", ""),
        narracion=raw["narracion"],
        visual=visual,
        texto_en_pantalla=raw.get("texto_en_pantalla"),
        audio=audio,
        inicio_aprox=raw.get("inicio_aprox"),
        duracion_seg_estimada=raw.get("duracion_seg"),
    )
