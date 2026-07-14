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


def test_karaoke_chunks_with_pop_and_kf(tmp_path: Path) -> None:
    dest = tmp_path / "caps.ass"
    write_ass([_plano("p1", 0.9, 2.7)], dest, transcript=_transcript())

    content = dest.read_text(encoding="utf-8")
    assert "Dialogue:" in content
    assert "\\kf" in content  # karaoke word timing
    assert "\\fscx72\\fscy72" in content  # pop de entrada (escala)
    assert "hola" in content and "prueba" in content
    # duración de "hola" absorbe el hueco hasta "mundo": 1.5-1.0 = 50 cs
    assert "{\\kf50}hola" in content


def test_captions_chunked_max_words(tmp_path: Path) -> None:
    # 5 palabras -> se parten en chunks de <=3
    words = [TranscriptWord(w, i * 0.5, i * 0.5 + 0.4) for i, w in
             enumerate(["uno", "dos", "tres", "cuatro", "cinco"])]
    dest = tmp_path / "caps.ass"
    write_ass([_plano("p1", 0.0, 3.0)], dest, transcript=Transcript(words=words))
    content = dest.read_text(encoding="utf-8")
    caption_lines = [l for l in content.splitlines() if ",Caption," in l]
    assert len(caption_lines) >= 2  # no cabe todo en un solo golpe


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


def test_cta_end_card_dialogue(tmp_path: Path) -> None:
    dest = tmp_path / "caps.ass"
    write_ass(
        [_plano("p1", 1.0, 3.0)], dest, transcript=_transcript(),
        cta_text="Sígueme para más", cta_start_seconds=10.0, cta_duration=3.0,
    )
    content = dest.read_text(encoding="utf-8")
    assert "SÍGUEME PARA MÁS" in content
    # el CTA aparece cerca de su tiempo de inicio (10s)
    assert "0:00:10" in content


def test_title_has_pop_no_box(tmp_path: Path) -> None:
    dest = tmp_path / "caps.ass"
    write_ass([_plano("p1", 0.5, 2.0)], dest, meta=GuionMeta(titulo="Prueba"))
    content = dest.read_text(encoding="utf-8")
    titulo_line = next(l for l in content.splitlines() if l.startswith("Style: Titulo"))
    fields = titulo_line.split(",")
    assert fields[15] == "1"  # BorderStyle=1 (borde+sombra, SIN caja)
    # el título entra con pop de escala, no plano
    titulo_dialog = next(l for l in content.splitlines() if ",Titulo," in l and "PRUEBA" in l)
    assert "\\fscx60\\fscy60" in titulo_dialog


def test_no_transcript_no_karaoke_but_valid_file(tmp_path: Path) -> None:
    dest = tmp_path / "caps.ass"
    write_ass([_plano("p1", 1.0, 3.0)], dest)
    content = dest.read_text(encoding="utf-8")
    assert "[Events]" in content
    assert "\\kf" not in content
