from pathlib import Path

from illustrated_narrator.domain.entities.plano import Plano, PlanoEstado, VisualSpec, VisualTipo
from illustrated_narrator.domain.services.retention_plan import Shot
from illustrated_narrator.domain.use_cases.generate_plano_images import GeneratePlanoImages
from illustrated_narrator.ports.image_generator import ImageGenerationRequest, ImageGeneratorPort


class _NullGenerator(ImageGeneratorPort):
    """Mismo comportamiento que NullImageGenerator: nunca genera, siempre falla."""

    def is_available(self) -> bool:
        return True

    def generate(self, request: ImageGenerationRequest, dest: Path) -> Path:
        raise RuntimeError("No se encontró medio real para esta toma y NARR_IMAGE_BACKEND=none")


def _plano(pid: str) -> Plano:
    return Plano(
        id=pid, seccion="hook", narracion="algo",
        visual=VisualSpec(tipo=VisualTipo.IMAGEN_IA, prompt_ia="algo"),
    )


def _shots(pid: str, total: int) -> list[Shot]:
    return [Shot(plano_id=pid, index=i, total=total) for i in range(total)]


def test_toma_extra_sin_medio_no_tira_el_plano_si_otras_ya_resolvieron(tmp_path: Path) -> None:
    images_dir = tmp_path / "images"
    images_dir.mkdir()
    plano = _plano("p03")
    shots = _shots("p03", 5)
    # Simula investigación de medios previa: tomas 1-4 ya tienen archivo real
    # en disco, la 5 no tiene nada (caso real: p03_5).
    for shot in shots[:4]:
        (images_dir / f"{shot.shot_id}.png").write_bytes(b"fake")

    use_case = GeneratePlanoImages(_NullGenerator(), "style", "", 20, 7.0, "sampler")
    report = use_case.execute([plano], images_dir, shots_by_plano={"p03": shots})

    assert report.failed == []
    assert plano in report.generated
    assert plano.estado == PlanoEstado.IMAGEN_GENERADA
    # La toma principal (index 0) sí resolvió, así que imagen_path apunta a esa.
    assert plano.imagen_path == str(images_dir / "p03_1.png")


def test_toma_principal_sin_medio_usa_otra_toma_resuelta_como_imagen_path(tmp_path: Path) -> None:
    images_dir = tmp_path / "images"
    images_dir.mkdir()
    plano = _plano("p07")
    shots = _shots("p07", 3)
    # La toma 0 (principal) es justo la que falta; la 1 y 2 sí tienen archivo.
    (images_dir / f"{shots[1].shot_id}.png").write_bytes(b"fake")
    (images_dir / f"{shots[2].shot_id}.png").write_bytes(b"fake")

    use_case = GeneratePlanoImages(_NullGenerator(), "style", "", 20, 7.0, "sampler")
    report = use_case.execute([plano], images_dir, shots_by_plano={"p07": shots})

    assert report.failed == []
    assert plano.estado == PlanoEstado.IMAGEN_GENERADA
    assert plano.imagen_path == str(images_dir / f"{shots[1].shot_id}.png")


def test_plano_sin_ninguna_toma_resuelta_si_falla(tmp_path: Path) -> None:
    images_dir = tmp_path / "images"
    images_dir.mkdir()
    plano = _plano("p09")
    shots = _shots("p09", 2)

    use_case = GeneratePlanoImages(_NullGenerator(), "style", "", 20, 7.0, "sampler")
    report = use_case.execute([plano], images_dir, shots_by_plano={"p09": shots})

    assert report.generated == []
    assert len(report.failed) == 1
    failed_plano, error = report.failed[0]
    assert failed_plano is plano
    assert plano.estado == PlanoEstado.FALLIDO
    assert "medio real" in error


def test_plano_de_una_sola_toma_sin_medio_sigue_fallando(tmp_path: Path) -> None:
    images_dir = tmp_path / "images"
    images_dir.mkdir()
    plano = _plano("p11")

    use_case = GeneratePlanoImages(_NullGenerator(), "style", "", 20, 7.0, "sampler")
    report = use_case.execute([plano], images_dir, shots_by_plano=None)

    assert report.generated == []
    assert len(report.failed) == 1
    assert plano.estado == PlanoEstado.FALLIDO
