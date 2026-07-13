"""Persistencia de la transcripción (transcript.json).

Transcribir es la etapa más cara; los subtítulos karaoke necesitan los
timestamps por palabra en CADA corrida (el ensamblado siempre se re-corre).
Guardar el transcript evita re-transcribir solo para re-subtitular.
"""

import json
from pathlib import Path

from illustrated_narrator.domain.entities.transcript import Transcript, TranscriptWord


def save_transcript(transcript: Transcript, path: Path) -> None:
    data = {
        "language": transcript.language,
        "words": [
            {"text": w.text, "start": w.start_seconds, "end": w.end_seconds}
            for w in transcript.words
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def load_transcript(path: Path) -> Transcript | None:
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return Transcript(
        words=[
            TranscriptWord(text=w["text"], start_seconds=w["start"], end_seconds=w["end"])
            for w in data.get("words", [])
        ],
        language=data.get("language"),
    )
