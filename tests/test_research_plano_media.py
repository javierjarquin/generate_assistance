from pathlib import Path

from illustrated_narrator.domain.entities.plano import Plano, VisualSpec, VisualTipo
from illustrated_narrator.domain.services.retention_plan import Shot
from illustrated_narrator.domain.use_cases.research_plano_media import ResearchPlanoMedia
from illustrated_narrator.ports.stock_media import MediaCandidate, StockImagePort


class _FakeSource(StockImagePort):
    """Fuente que siempre devuelve un único candidato con relevancia baja,
    para que _best_match no se quede con el primero y la ronda tenga que
    seguir consultando a las demás fuentes."""

    def __init__(self, name: str, tmp_path: Path) -> None:
        self._name = name
        self._tmp_path = tmp_path
        self.calls = 0

    def is_available(self) -> bool:
        return True

    def search(self, query: str, dest_dir: Path, count: int) -> list[MediaCandidate]:
        self.calls += 1
        dest = dest_dir / f"{self._name}.jpg"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"fake")
        return [
            MediaCandidate(
                path=dest,
                title=self._name,  # no relacionado con la query -> score bajo
                source=self._name,
                source_url=f"https://example.com/{self._name}",
                license="test",
            )
        ]


def _plano(id_: str = "p1") -> Plano:
    return Plano(
        id=id_, seccion="s", narracion="x",
        visual=VisualSpec(tipo=VisualTipo.IMAGEN_IA, prompt_ia="p", busqueda_medios="bosque"),
    )


class _GeoAwareSource(StockImagePort):
    """Solo devuelve un candidato relevante si la query incluye "mexico" --
    simula que la búsqueda original (sin país) no encuentra nada bueno pero
    la ensanchada con el país sí."""

    def is_available(self) -> bool:
        return True

    def search(self, query: str, dest_dir: Path, count: int) -> list[MediaCandidate]:
        if "mexico" not in query.lower():
            return []
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / "match.jpg"
        dest.write_bytes(b"fake")
        return [MediaCandidate(
            path=dest, title="prison cell block Mexico", source="test",
            source_url="https://example.com/match", license="test",
        )]


def test_search_all_queries_every_source_not_just_the_first(tmp_path: Path) -> None:
    source_a = _FakeSource("a", tmp_path)
    source_b = _FakeSource("b", tmp_path)
    source_c = _FakeSource("c", tmp_path)
    # candidates_per_shot=1: la primera fuente sola ya llena la cuota -- si
    # quedara el corte temprano, b y c nunca se consultarían.
    research = ResearchPlanoMedia(
        sources_default=[source_a, source_b, source_c],
        sources_historico=[],
        candidates_per_shot=1,
        min_score=0.0,
    )

    plano = _plano()
    shots_by_plano = {plano.id: [Shot(plano_id=plano.id, index=0, total=1)]}
    research.execute(
        [plano], tmp_path / "images", tmp_path / "media", tmp_path / "media" / "manifest.json",
        shots_by_plano,
    )

    # las 3 fuentes deben haber sido consultadas, no solo la primera
    assert source_a.calls == 1
    assert source_b.calls == 1
    assert source_c.calls == 1


def test_geo_fallback_usa_el_pais_del_guion_cuando_nada_mas_encuentra(tmp_path: Path) -> None:
    research = ResearchPlanoMedia(
        sources_default=[_GeoAwareSource()], sources_historico=[],
        candidates_per_shot=3, min_score=0.5,
    )
    plano = Plano(
        id="p06", seccion="s", narracion="x",
        visual=VisualSpec(
            tipo=VisualTipo.IMAGEN_IA, prompt_ia="prison cell block",
            busqueda_medios="prison cell block",
        ),
    )
    shots_by_plano = {plano.id: [Shot(plano_id=plano.id, index=0, total=1)]}

    report = research.execute(
        [plano], tmp_path / "images", tmp_path / "media", tmp_path / "media" / "manifest.json",
        shots_by_plano, pais_default="Mexico",
    )

    assert report.shots_resolved == 1
    assert (tmp_path / "images" / "p06.png").exists()


def test_geo_fallback_usa_pais_del_plano_por_encima_del_default_del_guion(tmp_path: Path) -> None:
    research = ResearchPlanoMedia(
        sources_default=[_GeoAwareSource()], sources_historico=[],
        candidates_per_shot=3, min_score=0.5,
    )
    plano = Plano(
        id="p09", seccion="s", narracion="x",
        visual=VisualSpec(
            tipo=VisualTipo.IMAGEN_IA, prompt_ia="prison cell block",
            busqueda_medios="prison cell block", pais="Mexico",
        ),
    )
    shots_by_plano = {plano.id: [Shot(plano_id=plano.id, index=0, total=1)]}

    # pais_default distinto ("Francia") -- debe ganar el pais del plano
    report = research.execute(
        [plano], tmp_path / "images", tmp_path / "media", tmp_path / "media" / "manifest.json",
        shots_by_plano, pais_default="Francia",
    )

    assert report.shots_resolved == 1


def test_sin_pais_no_hay_fallback_geografico(tmp_path: Path) -> None:
    research = ResearchPlanoMedia(
        sources_default=[_GeoAwareSource()], sources_historico=[],
        candidates_per_shot=3, min_score=0.5,
    )
    plano = Plano(
        id="p06", seccion="s", narracion="x",
        visual=VisualSpec(
            tipo=VisualTipo.IMAGEN_IA, prompt_ia="prison cell block",
            busqueda_medios="prison cell block",
        ),
    )
    shots_by_plano = {plano.id: [Shot(plano_id=plano.id, index=0, total=1)]}

    report = research.execute(
        [plano], tmp_path / "images", tmp_path / "media", tmp_path / "media" / "manifest.json",
        shots_by_plano,
    )

    assert report.shots_resolved == 0
