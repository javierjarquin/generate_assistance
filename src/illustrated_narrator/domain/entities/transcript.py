from dataclasses import dataclass, field


@dataclass(frozen=True)
class TranscriptWord:
    text: str
    start_seconds: float
    end_seconds: float


@dataclass(frozen=True)
class Transcript:
    words: list[TranscriptWord] = field(default_factory=list)
    language: str | None = None
