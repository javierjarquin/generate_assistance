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
from illustrated_narrator.domain.services.media_relevance import (
    broaden_query,
    continente_de,
    derive_query,
    extract_proper_nouns,
    relevance_score,
    title_specificity,
)
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
        pais_default: str | None = None,
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
            # Sembrado desde el manifest existente: si esta corrida solo
            # reinvestiga las tomas que fallaron antes (las demas se saltean
            # abajo porque ya tienen archivo en disco), este set arrancaba
            # vacio y no sabia qué URL ya usaron sus tomas hermanas -- una
            # toma reintentada podia elegir la MISMA foto que otra toma del
            # mismo plano ya resuelta, repitiendo imagen dentro de un plano
            # (confirmado en una corrida real: p03 toma 1 y toma 4 terminaron
            # con el mismo pexels_33039807.jpg).
            used_urls: set[str] = {
                entry["chosen"]["source_url"]
                for shot_id, entry in manifest.items()
                if entry.get("chosen") and (shot_id == plano.id or shot_id.startswith(f"{plano.id}_"))
            }
            # Nombres propios ya cubiertos por una toma hermana de este plano
            # -- ver _proper_noun_fallback: sin esto, si el plano menciona
            # varias figuras públicas, la primera mencionada "acapara" todas
            # las tomas que caen a este fallback (mientras tenga fotos
            # disponibles) y las demás nunca se intentan.
            used_names: set[str] = set()
            # Mejor candidato real ya elegido por una toma hermana de este
            # plano -- último recurso si una toma se queda sin NINGÚN match
            # propio tras agotar búsqueda + nombre propio + país/continente.
            # Sin esto, un plano con más tomas que fotos realmente distintas
            # disponibles (frecuente: una query genérica solo tiene 1-2
            # candidatos buenos pero el plano tiene 4-5 tomas) deja las
            # tomas sobrantes "sin_medio" -- confirmado en corridas reales
            # (guion-cassez-vallarta) que eso dispara escalada a Claude cada
            # vez. Repetir una foto real dentro del mismo plano es mejor que
            # una toma vacía.
            best_reusable: MediaCandidate | None = None

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
                if chosen is None:
                    fallback = self._proper_noun_fallback(plano, plano_media_dir, used_urls, used_names)
                    if fallback is not None:
                        query, fb_candidates, chosen = fallback
                        candidates = candidates + fb_candidates
                if chosen is None:
                    fallback = self._geo_fallback(
                        plano, query, sources, plano_media_dir, used_urls, pais_default
                    )
                    if fallback is not None:
                        query, fb_candidates, chosen = fallback
                        candidates = candidates + fb_candidates
                if chosen is None and best_reusable is not None:
                    chosen = best_reusable
                record_shot_result(manifest, shot.shot_id, query, candidates, chosen)
                if chosen is not None:
                    used_urls.add(chosen.source_url)
                    best_reusable = chosen
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
        # Desempate por especificidad del título: con varios candidatos
        # empatados en score, preferir el título más corto/limpio en vez de
        # quedarse con el primero que apareció (ver title_specificity).
        scored = sorted(
            available,
            key=lambda c: (relevance_score(query, c.title), -title_specificity(c.title)),
            reverse=True,
        )
        best = scored[0]
        if relevance_score(query, best.title) < self._effective_min_score(best):
            return None
        return best

    # Un nombre propio (persona/lugar) casi literal en el título es señal
    # mucho más fuerte que el match genérico de _effective_min_score -- pero
    # tiene que ser el nombre COMPLETO, no solo una palabra. Con el umbral
    # anterior (0.5) un nombre de pila comun bastaba para dar falso positivo:
    # "Alberto Bazbaz" contra "Alberto Fernández Blanco" da exactamente 0.5
    # (solo "Alberto" matchea) y una persona real sin ninguna relación con el
    # plano terminaba en el video (confirmado en una corrida real, caso
    # guion-paulette). "Cecilio Chi" contra "Esculturas de Cecilio Chí en
    # Chetumal" sigue dando 1.0 con las dos palabras, así que subir el
    # umbral a exigir el nombre completo no pierde ese caso bueno.
    _PROPER_NOUN_MIN_SCORE = 1.0

    def _proper_noun_fallback(
        self, plano: Plano, dest_dir: Path, used_urls: set[str], used_names: set[str]
    ) -> tuple[str, list[MediaCandidate], MediaCandidate] | None:
        """Si la búsqueda principal (derivada del prompt_ia en inglés, pensado
        para dirigir un modelo de imagen) no encontró nada relevante, prueba
        el/los nombres propios reales del plano (narracion/descripcion, en
        español) directo contra Wikimedia. Mismo principio que
        archivo_historico pero automático para CUALQUIER plano -- confirmado
        en un video real: la query genérica no encontraba nada para "Cecilio
        Chi", pero buscando su nombre aparecían fotos reales de su estatua."""
        if not self._sources_historico:
            return None
        names = extract_proper_nouns(plano.narracion, plano.visual.descripcion)
        # Prioriza nombres que ninguna toma hermana de este plano ya usó --
        # si no, cuando un plano menciona varias figuras públicas, la primera
        # mencionada en el texto "acapara" todas las tomas que caen a este
        # fallback mientras tenga fotos disponibles, y las demás nunca se
        # intentan (confirmado en corrida real: un plano mencionaba a Isabel
        # Miranda de Wallace Y a Felipe Calderón, pero como Wikimedia tenía
        # más de una foto candidata con "Isabel Miranda" en el título, las
        # dos tomas que necesitaban este fallback se resolvieron ahí y
        # "Felipe Calderón" -- correctamente extraído -- nunca se probó).
        ordered_names = sorted(names, key=lambda n: n in used_names)
        for name in ordered_names:
            candidates = self._search_all(self._sources_historico, name, dest_dir)
            available = [c for c in candidates if c.source_url not in used_urls]
            if not available:
                continue
            scored = sorted(
                available,
                key=lambda c: (relevance_score(name, c.title), -title_specificity(c.title)),
                reverse=True,
            )
            best = scored[0]
            if relevance_score(name, best.title) >= self._PROPER_NOUN_MIN_SCORE:
                used_names.add(name)
                return name, candidates, best
        return None

    def _geo_fallback(
        self, plano: Plano, query: str, sources: list[StockImagePort],
        dest_dir: Path, used_urls: set[str], pais_default: str | None,
    ) -> tuple[str, list[MediaCandidate], MediaCandidate] | None:
        """Último recurso antes de dejar la toma sin medio: reintenta la
        MISMA query (conserva qué es la escena) ensanchada primero con el
        país del plano (meta.pais del guion, o visual.pais si este plano
        puntual pasa en otro lugar) y, si tampoco encuentra nada relevante,
        con su continente -- más rango de búsqueda sin perder el contenido.
        Reduce además los falsos positivos de país incoherente (ver
        _SENSITIVE_BLOCKLIST): una query ya acotada a "Mexico" difícilmente
        devuelve Alcatraz o Auschwitz como mejor resultado."""
        pais = plano.visual.pais or pais_default
        intentos = [broaden_query(query, pais), broaden_query(query, continente_de(pais))]
        for query_ampliada in intentos:
            if not query_ampliada:
                continue
            candidates = self._search_all(sources, query_ampliada, dest_dir)
            available = [c for c in candidates if c.source_url not in used_urls]
            if not available:
                continue
            scored = sorted(
                available,
                key=lambda c: (relevance_score(query_ampliada, c.title), -title_specificity(c.title)),
                reverse=True,
            )
            best = scored[0]
            if relevance_score(query_ampliada, best.title) >= self._effective_min_score(best):
                return query_ampliada, candidates, best
        return None

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
