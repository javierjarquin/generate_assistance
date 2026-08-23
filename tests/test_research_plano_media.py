import json
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


class _NamedFiguresSource(StockImagePort):
    """Simula Wikimedia respondiendo distinto según el nombre propio buscado:
    dos candidatos para "Isabel Miranda" (para poder cubrir 2 tomas con ese
    solo nombre si nada lo evita) y uno para "Felipe Calderón"."""

    def is_available(self) -> bool:
        return True

    def search(self, query: str, dest_dir: Path, count: int) -> list[MediaCandidate]:
        dest_dir.mkdir(parents=True, exist_ok=True)
        if query == "Isabel Miranda":
            candidates = []
            for i, title in enumerate(["Isabel Miranda de Wallace", "Isabel Miranda Otra Persona"]):
                dest = dest_dir / f"isabel_{i}.jpg"
                dest.write_bytes(b"fake")
                candidates.append(MediaCandidate(
                    path=dest, title=title, source="wikimedia",
                    source_url=f"https://example.com/isabel_{i}", license="test",
                ))
            return candidates
        if query == "Felipe Calderón":
            dest = dest_dir / "calderon.jpg"
            dest.write_bytes(b"fake")
            return [MediaCandidate(
                path=dest, title="Felipe Calderón", source="wikimedia",
                source_url="https://example.com/calderon", license="test",
            )]
        return []


def test_proper_noun_fallback_reparte_entre_varias_figuras_del_mismo_plano(tmp_path: Path) -> None:
    """Un plano que menciona a dos figuras públicas y tiene tomas de sobra
    para cubrir ambas no debe dejar a la segunda sin foto solo porque la
    primera mencionada ya tenía candidatos disponibles (bug real: "Felipe
    Calderón" nunca se intentaba porque "Isabel Miranda" ya cubría las dos
    tomas que caían al fallback de nombre propio)."""
    research = ResearchPlanoMedia(
        sources_default=[], sources_historico=[_NamedFiguresSource()],
        candidates_per_shot=3, min_score=0.5,
    )
    plano = Plano(
        id="p04", seccion="s",
        narracion="Isabel Miranda viajó junto a Felipe Calderón a la capital.",
        visual=VisualSpec(tipo=VisualTipo.IMAGEN_IA, prompt_ia="bosque", busqueda_medios="bosque"),
    )
    shots_by_plano = {plano.id: [
        Shot(plano_id=plano.id, index=0, total=2),
        Shot(plano_id=plano.id, index=1, total=2),
    ]}

    manifest_path = tmp_path / "media" / "manifest.json"
    report = research.execute(
        [plano], tmp_path / "images", tmp_path / "media", manifest_path, shots_by_plano,
    )

    assert report.shots_resolved == 2
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    titles = {entry["chosen"]["title"] for entry in manifest.values() if entry.get("chosen")}
    assert "Felipe Calderón" in titles


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
