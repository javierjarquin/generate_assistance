from pathlib import Path

from illustrated_narrator.adapters.video.ass_writer import write_ass
from illustrated_narrator.domain.entities.guion import GuionMeta
from illustrated_narrator.domain.entities.plano import Plano, VisualSpec, VisualTipo
from illustrated_narrator.domain.entities.transcript import Transcript, TranscriptWord


def _plano(id_: str, start: float, end: float, texto: str | None = None) -> Plano:
    p = Plano(
        id=id_, seccion="s", narracion="hola mundo prueba",
        visual=VisualSpec(tipo=VisualTipo.IMAGEN_IA, prompt_ia="x"),
        texto_en_pantalla=texto,
    )
    p.inicio_real_seg = start
    p.fin_real_seg = end
    return p


def _transcript() -> Transcript:
    return Transcript(
        words=[
            TranscriptWord("hola", 1.0, 1.4),
            TranscriptWord("mundo", 1.5, 2.0),
            TranscriptWord("prueba", 2.1, 2.6),
        ],
        language="es",
    )


def test_karaoke_lines_with_kf_tags(tmp_path: Path) -> None:
    dest = tmp_path / "caps.ass"
    write_ass([_plano("p1", 0.9, 2.7)], dest, transcript=_transcript())

    content = dest.read_text(encoding="utf-8")
    assert "Dialogue:" in content
    assert "\\kf" in content  # karaoke word timing
    assert "hola" in content and "prueba" in content
    # duración de "hola" absorbe el hueco hasta "mundo": 1.5-1.0 = 50 cs
    assert "{\\kf50}hola" in content


def test_title_hook_from_meta(tmp_path: Path) -> None:
    dest = tmp_path / "caps.ass"
    write_ass(
        [_plano("p1", 0.5, 2.0)], dest,
        transcript=_transcript(),
        meta=GuionMeta(titulo="El Faro de Alejandría"),
    )
    content = dest.read_text(encoding="utf-8")
    assert "EL FARO DE ALEJANDRÍA" in content
    assert "Titulo" in content


def test_rotulo_from_texto_en_pantalla(tmp_path: Path) -> None:
    dest = tmp_path / "caps.ass"
    write_ass([_plano("p1", 1.0, 3.0, texto="100 METROS")], dest)
    content = dest.read_text(encoding="utf-8")
    assert "100 METROS" in content


def test_no_transcript_no_karaoke_but_valid_file(tmp_path: Path) -> None:
    dest = tmp_path / "caps.ass"
    write_ass([_plano("p1", 1.0, 3.0)], dest)
    content = dest.read_text(encoding="utf-8")
    assert "[Events]" in content
    assert "\\kf" not in content
