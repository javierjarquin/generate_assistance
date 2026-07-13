from pathlib import Path

from illustrated_narrator.domain.entities.transcript import Transcript, TranscriptWord
from illustrated_narrator.domain.services.transcript_store import load_transcript, save_transcript


def test_roundtrip(tmp_path: Path) -> None:
    original = Transcript(
        words=[TranscriptWord("hola", 0.5, 0.9), TranscriptWord("mundo", 1.0, 1.4)],
        language="es",
    )
    path = tmp_path / "transcript.json"

    save_transcript(original, path)
    loaded = load_transcript(path)

    assert loaded is not None
    assert loaded.language == "es"
    assert [w.text for w in loaded.words] == ["hola", "mundo"]
    assert loaded.words[1].start_seconds == 1.0


def test_load_missing_returns_none(tmp_path: Path) -> None:
    assert load_transcript(tmp_path / "no_existe.json") is None
