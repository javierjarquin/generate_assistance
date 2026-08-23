from pathlib import Path

from illustrated_narrator.domain.entities.plano import Plano, PlanoEstado, VisualSpec, VisualTipo
from illustrated_narrator.domain.services.retention_plan import Shot
from illustrated_narrator.domain.use_cases.generate_plano_images import GeneratePlanoImages
from illustrated_narrator.ports.image_generator import ImageGenerationRequest, ImageGeneratorPort
from illustrated_narrator.ports.video_generator import VideoGenerationRequest, VideoGeneratorPort


class _NullGenerator(ImageGeneratorPort):
    """Mismo comportamiento que NullImageGenerator: nunca genera, siempre falla."""

    def is_available(self) -> bool:
        return True

    def generate(self, request: ImageGenerationRequest, dest: Path) -> Path:
        raise RuntimeError("No se encontró medio real para esta toma y NARR_IMAGE_BACKEND=none")


class _FakeVideoGenerator(VideoGeneratorPort):
    def __init__(self, available: bool = True, fail: bool = False) -> None:
        self._available = available
        self.fail = fail
        self.calls: list[VideoGenerationRequest] = []

    def is_available(self) -> bool:
        return self._available

    def generate(self, request: VideoGenerationRequest, dest: Path) -> Path:
        self.calls.append(request)
        if self.fail:
            raise RuntimeError("AnimateLCM se cayó")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"fake-mp4")
        return dest


def _plano(pid: str, tipo: VisualTipo = VisualTipo.IMAGEN_IA) -> Plano:
    return Plano(
        id=pid, seccion="hook", narracion="algo",
        visual=VisualSpec(tipo=tipo, prompt_ia="algo"),
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


def test_video_fallback_resuelve_plano_sin_ningun_medio_real(tmp_path: Path) -> None:
    images_dir = tmp_path / "images"
    media_dir = tmp_path / "media"
    images_dir.mkdir()
    plano = _plano("p11", tipo=VisualTipo.GRAFICO_MOVIMIENTO)
    shots = _shots("p11", 1)
    video_gen = _FakeVideoGenerator()

    use_case = GeneratePlanoImages(
        _NullGenerator(), "style", "", 20, 7.0, "sampler",
        video_generator=video_gen, max_video_fallback_planos=2, max_video_fallback_seconds=4.0,
    )
    report = use_case.execute([plano], images_dir, shots_by_plano={"p11": shots}, media_dir=media_dir)

    assert report.failed == []
    assert plano.estado == PlanoEstado.IMAGEN_GENERADA
    assert plano.imagen_path == str(media_dir / "videos" / "p11.mp4")
    assert (media_dir / "videos" / "p11.mp4").exists()
    assert len(video_gen.calls) == 1
    assert video_gen.calls[0].duration_seconds == 4.0
    # SIN style_suffix: confirmado en una prueba real que un prompt largo
    # (prompt_ia + el sufijo de estilo de las imágenes fijas) se queda sin
    # VRAM en esta GPU -- no reagregarlo al prompt del video.
    assert video_gen.calls[0].prompt == "algo"
    assert "style" not in video_gen.calls[0].prompt


def test_video_fallback_nunca_para_archivo_historico(tmp_path: Path) -> None:
    images_dir = tmp_path / "images"
    media_dir = tmp_path / "media"
    images_dir.mkdir()
    plano = _plano("p04", tipo=VisualTipo.ARCHIVO_HISTORICO)
    shots = _shots("p04", 1)
    video_gen = _FakeVideoGenerator()

    use_case = GeneratePlanoImages(
        _NullGenerator(), "style", "", 20, 7.0, "sampler",
        video_generator=video_gen, max_video_fallback_planos=2,
    )
    report = use_case.execute([plano], images_dir, shots_by_plano={"p04": shots}, media_dir=media_dir)

    assert video_gen.calls == []
    assert plano.estado == PlanoEstado.FALLIDO
    assert len(report.failed) == 1


def test_video_fallback_respeta_el_presupuesto_por_corrida(tmp_path: Path) -> None:
    images_dir = tmp_path / "images"
    media_dir = tmp_path / "media"
    images_dir.mkdir()
    plano_a = _plano("p05")
    plano_b = _plano("p08")
    video_gen = _FakeVideoGenerator()

    use_case = GeneratePlanoImages(
        _NullGenerator(), "style", "", 20, 7.0, "sampler",
        video_generator=video_gen, max_video_fallback_planos=1,
    )
    report = use_case.execute(
        [plano_a, plano_b], images_dir,
        shots_by_plano={"p05": _shots("p05", 1), "p08": _shots("p08", 1)},
        media_dir=media_dir,
    )

    assert len(video_gen.calls) == 1  # solo el primero consume el presupuesto
    assert plano_a.estado == PlanoEstado.IMAGEN_GENERADA
    assert plano_b.estado == PlanoEstado.FALLIDO
    assert len(report.failed) == 1


def test_video_fallback_desactivado_por_default(tmp_path: Path) -> None:
    images_dir = tmp_path / "images"
    images_dir.mkdir()
    plano = _plano("p11", tipo=VisualTipo.GRAFICO_MOVIMIENTO)

    use_case = GeneratePlanoImages(_NullGenerator(), "style", "", 20, 7.0, "sampler")
    report = use_case.execute([plano], images_dir, shots_by_plano={"p11": _shots("p11", 1)})

    assert plano.estado == PlanoEstado.FALLIDO
    assert len(report.failed) == 1


def test_video_fallback_si_el_generador_tambien_falla_queda_fallido(tmp_path: Path) -> None:
    images_dir = tmp_path / "images"
    media_dir = tmp_path / "media"
    images_dir.mkdir()
    plano = _plano("p11", tipo=VisualTipo.IMAGEN_IA)
    video_gen = _FakeVideoGenerator(fail=True)

    use_case = GeneratePlanoImages(
        _NullGenerator(), "style", "", 20, 7.0, "sampler",
        video_generator=video_gen, max_video_fallback_planos=2,
    )
    report = use_case.execute(
        [plano], images_dir, shots_by_plano={"p11": _shots("p11", 1)}, media_dir=media_dir,
    )

    assert plano.estado == PlanoEstado.FALLIDO
    assert len(report.failed) == 1
    assert "AnimateLCM se cayó" in report.failed[0][1]
