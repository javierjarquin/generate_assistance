"""Investiga medios reales (fotos de stock/archivo) para los shots de cada
plano ANTES de generar con IA.

Capa de enriquecimiento, no reemplazo: corre para CUALQUIER plano sin filtrar
por visual.tipo (mismo principio que retention_plan.py — estándar por
defecto, no opt-in). Un shot sin candidato relevante simplemente sigue el
camino de siempre: generate_plano_images.py lo genera con IA porque el
archivo en images_dir no existe. visual.tipo solo reordena qué fuente se
prueba primero (archivo_historico prioriza Wikimedia Commons).
"""

import logging
from dataclasses import dataclass
from pathlib import Path

from illustrated_narrator.domain.entities.plano import Plano, VisualTipo
from illustrated_narrator.domain.services.media_manifest import (
    load_manifest,
    record_shot_result,
    save_manifest,
)
from illustrated_narrator.domain.services.media_relevance import derive_query, relevance_score
from illustrated_narrator.domain.services.retention_plan import Shot
from illustrated_narrator.domain.services.shot_assets import (
    is_video_file,
    resolve_shot_asset,
    shot_image_path,
    shot_video_path,
)
from illustrated_narrator.ports.stock_media import MediaCandidate, StockImagePort

logger = logging.getLogger(__name__)


@dataclass
class ResearchMediaReport:
    shots_resolved: int = 0


class ResearchPlanoMedia:
    def __init__(
        self,
        sources_default: list[StockImagePort],
        sources_historico: list[StockImagePort],
        candidates_per_shot: int = 3,
        min_score: float = 0.35,
    ) -> None:
        self._sources_default = sources_default
        self._sources_historico = sources_historico
        self._candidates_per_shot = candidates_per_shot
        self._min_score = min_score

    def execute(
        self,
        planos: list[Plano],
        images_dir: Path,
        media_dir: Path,
        manifest_path: Path,
        shots_by_plano: dict[str, list[Shot]],
    ) -> ResearchMediaReport:
        report = ResearchMediaReport()
        if not self._sources_default and not self._sources_historico:
            return report
        manifest = load_manifest(manifest_path)

        for plano in planos:
            shots = shots_by_plano.get(plano.id) or [Shot(plano_id=plano.id, index=0, total=1)]
            sources = (
                self._sources_historico
                if plano.visual.tipo == VisualTipo.ARCHIVO_HISTORICO
                else self._sources_default
            ) or (self._sources_default or self._sources_historico)
            plano_media_dir = media_dir / plano.id
            used_urls: set[str] = set()

            for shot in shots:
                if resolve_shot_asset(images_dir, media_dir, shot) is not None:
                    continue  # ya tiene asset (real o IA de una corrida previa)

                manual = self._manual_override(plano_media_dir, shot)
                if manual is not None:
                    dest = (
                        shot_video_path(media_dir, shot)
                        if is_video_file(manual)
                        else shot_image_path(images_dir, shot)
                    )
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(manual.read_bytes())
                    report.shots_resolved += 1
                    continue

                query = derive_query(
                    plano.visual.prompt_ia, plano.visual.descripcion, plano.visual.busqueda_medios
                )
                candidates = self._search_all(sources, query, plano_media_dir)
                chosen = self._best_match(query, candidates, used_urls)
                record_shot_result(manifest, shot.shot_id, query, candidates, chosen)
                if chosen is not None:
                    used_urls.add(chosen.source_url)
                    dest = (
                        shot_video_path(media_dir, shot)
                        if chosen.media_type == "video"
                        else shot_image_path(images_dir, shot)
                    )
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(chosen.path.read_bytes())
                    report.shots_resolved += 1

        save_manifest(manifest, manifest_path)
        return report

    def _search_all(
        self, sources: list[StockImagePort], query: str, dest_dir: Path
    ) -> list[MediaCandidate]:
        if not query:
            return []
        candidates: list[MediaCandidate] = []
        for source in sources:
            # Se consultan TODAS las fuentes (no solo hasta llenar la cuota):
            # con fotos + video + archivo como fuentes, cortar en la primera
            # que responda dejaría al video sin oportunidad de competir por
            # relevancia contra las fotos.
            try:
                found = source.search(query, dest_dir, self._candidates_per_shot)
            except Exception as exc:  # noqa: BLE001 — una fuente caída no frena la investigación
                logger.warning("Fuente de medios falló para '%s' (%s)", query, exc)
                continue
            candidates.extend(found)
        return candidates

    def _best_match(
        self, query: str, candidates: list[MediaCandidate], used_urls: set[str]
    ) -> MediaCandidate | None:
        available = [c for c in candidates if c.source_url not in used_urls]
        if not available:
            return None
        scored = sorted(
            available, key=lambda c: relevance_score(query, c.title), reverse=True
        )
        best = scored[0]
        if relevance_score(query, best.title) < self._effective_min_score(best):
            return None
        return best

    def _effective_min_score(self, candidate: MediaCandidate) -> float:
        # Pexels ya hace su propio matching semantico contra la query en el
        # servidor (devuelve resultados ordenados por relevancia real, no por
        # coincidencia de texto) -- nuestro relevance_score es un parche
        # pensado para el buscador de texto plano de Wikimedia (titulos
        # ruidosos, a veces en otro idioma). Aplicarle el MISMO umbral literal
        # a Pexels rechazaba resultados genuinamente buenos solo porque el
        # titulo no repetia las palabras de la query (visto en una corrida
        # real: "shooting star" / "lunar surface" para una query de
        # "asteroid" -- contenido correcto, vocabulario distinto).
        if candidate.source in ("pexels", "pexels_video"):
            return min(self._min_score, 0.22)
        return self._min_score

    @staticmethod
    def _manual_override(plano_media_dir: Path, shot: Shot) -> Path | None:
        if not plano_media_dir.exists():
            return None
        for pattern in (f"elegido_{shot.index + 1}.*", "elegido.*"):
            matches = sorted(plano_media_dir.glob(pattern))
            if matches:
                return matches[0]
        return None
