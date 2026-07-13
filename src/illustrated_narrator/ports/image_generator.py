from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ImageGenerationRequest:
    prompt: str
    label: str = ""  # texto humano (español) para backends que dibujan texto, ej. placeholder
    negative_prompt: str = ""
    width: int = 512
    height: int = 512
    steps: int = 20
    cfg_scale: float = 7.0
    sampler_name: str = "DPM++ 2M Karras"
    seed: int = -1


class ImageGeneratorPort(ABC):
    @abstractmethod
    def generate(self, request: ImageGenerationRequest, dest: Path) -> Path: ...

    @abstractmethod
    def is_available(self) -> bool: ...
