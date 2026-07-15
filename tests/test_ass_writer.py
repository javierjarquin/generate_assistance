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
    # el título largo se envuelve (\\N entre palabras); comparar sin saltos
    assert "EL FARO DE ALEJANDRÍA" in content.replace("\\N", " ")
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


def test_gancho_overrides_titulo(tmp_path: Path) -> None:
    dest = tmp_path / "caps.ass"
    write_ass(
        [_plano("p1", 0.5, 2.0)], dest,
        meta=GuionMeta(titulo="El Faro", gancho="¿Cómo cayó la torre más alta?"),
    )
    content = dest.read_text(encoding="utf-8").replace("\\N", " ")
    assert "¿CÓMO CAYÓ LA TORRE MÁS ALTA?" in content
    assert "EL FARO" not in content  # el gancho reemplaza al título


def test_custom_accent_color_reflected_in_caption_style(tmp_path: Path) -> None:
    dest = tmp_path / "caps.ass"
    write_ass([_plano("p1", 0.9, 2.7)], dest, transcript=_transcript(), accent_color_ass="&H00FF00FF")
    content = dest.read_text(encoding="utf-8")
    caption_line = next(l for l in content.splitlines() if l.startswith("Style: Caption"))
    assert "&H00FF00FF" in caption_line
    assert "&H0000E8FF" not in caption_line


def test_default_accent_color_unchanged(tmp_path: Path) -> None:
    dest = tmp_path / "caps.ass"
    write_ass([_plano("p1", 0.9, 2.7)], dest, transcript=_transcript())
    content = dest.read_text(encoding="utf-8")
    caption_line = next(l for l in content.splitlines() if l.startswith("Style: Caption"))
    assert "&H0000E8FF" in caption_line


def test_time_offset_shifts_all_timestamps(tmp_path: Path) -> None:
    dest = tmp_path / "caps.ass"
    write_ass(
        [_plano("p1", 1.0, 3.0, texto="100 METROS")], dest,
        transcript=_transcript(), meta=GuionMeta(titulo="Prueba"),
        time_offset_seconds=2.0,
    )
    content = dest.read_text(encoding="utf-8")
    # gancho/título arranca en 0.15+2.0=2.15 en vez de 0.15
    assert "Dialogue: 1,0:00:02.15,0:00:04.60,Titulo" in content
    # rótulo (texto_en_pantalla) usa inicio_real_seg + offset: 1.0+2.0=3.0
    assert "Dialogue: 0,0:00:03.00,0:00:05.00,Rotulo" in content
    # karaoke: primera palabra "hola" empieza en 1.0+2.0=3.0
    assert "Dialogue: 0,0:00:03.00" in content


def test_chunk_does_not_end_on_function_word(tmp_path: Path) -> None:
    # "pero lo que ningún" -> el chunk no debe terminar en "pero" ni "lo"
    words = [
        TranscriptWord("sobrevivió", 0.0, 0.5), TranscriptWord("pero", 0.6, 0.8),
        TranscriptWord("lo", 0.9, 1.0), TranscriptWord("que", 1.1, 1.2),
        TranscriptWord("ningún", 1.3, 1.6),
    ]
    dest = tmp_path / "caps.ass"
    write_ass([_plano("p1", 0.0, 2.0)], dest, transcript=Transcript(words=words))
    content = dest.read_text(encoding="utf-8")
    caption_lines = [l for l in content.splitlines() if ",Caption," in l]
    # ninguna línea de caption debe terminar en una palabra función
    for line in caption_lines:
        payload = line.split(",,", 1)[1]
        last = payload.rstrip("\n").split()[-1].strip(".,;:!?")
        assert last.lower() not in {"pero", "lo", "que"}
