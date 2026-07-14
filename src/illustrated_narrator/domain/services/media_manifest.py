"""Persistencia del manifest de medios reales encontrados (media/manifest.json):
qué se buscó, qué se eligió y qué se descartó, con licencia/autor/url — insumo
para créditos y para que el usuario revise/reemplace un candidato mal elegido.
"""

import json
from pathlib import Path

from illustrated_narrator.ports.stock_media import MediaCandidate


def _candidate_to_dict(candidate: MediaCandidate) -> dict:
    return {
        "path": str(candidate.path),
        "title": candidate.title,
        "source": candidate.source,
        "source_url": candidate.source_url,
        "license": candidate.license,
        "author": candidate.author,
    }


def load_manifest(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def record_shot_result(
    manifest: dict,
    shot_id: str,
    query: str,
    candidates: list[MediaCandidate],
    chosen: MediaCandidate | None,
) -> None:
    manifest[shot_id] = {
        "query": query,
        "chosen": _candidate_to_dict(chosen) if chosen else None,
        "candidates": [_candidate_to_dict(c) for c in candidates],
    }


def save_manifest(manifest: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
