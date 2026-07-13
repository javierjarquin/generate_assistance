"""Configuración por variables de entorno, con soporte de archivo .env."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class Settings:
    projects_dir: Path
    log_level: str
    ffmpeg_path: str
    video_encoder: str
    whisper_model: str
    whisper_cpu_threads: int
    whisper_language: str | None
    a1111_base_url: str
    sd_negative_prompt: str
    sd_steps: int
    sd_cfg_scale: float
    sd_sampler: str
    style_suffix: str
    target_fps: int
    xfade_duration: float


def load_settings() -> Settings:
    load_dotenv()
    language = os.getenv("NARR_WHISPER_LANGUAGE", "").strip()
    return Settings(
        projects_dir=Path(os.getenv("NARR_PROJECTS_DIR", _PROJECT_ROOT / "projects")),
        log_level=os.getenv("NARR_LOG_LEVEL", "INFO").upper(),
        ffmpeg_path=os.getenv("NARR_FFMPEG_PATH", "ffmpeg"),
        video_encoder=os.getenv("NARR_VIDEO_ENCODER", "auto"),
        whisper_model=os.getenv("NARR_WHISPER_MODEL", "small"),
        whisper_cpu_threads=int(os.getenv("NARR_WHISPER_CPU_THREADS", "0")),
        whisper_language=language or None,
        a1111_base_url=os.getenv("NARR_A1111_BASE_URL", "http://127.0.0.1:7860"),
        sd_negative_prompt=os.getenv(
            "NARR_SD_NEGATIVE_PROMPT", "blurry, low quality, deformed, watermark, text"
        ),
        sd_steps=int(os.getenv("NARR_SD_STEPS", "20")),
        sd_cfg_scale=float(os.getenv("NARR_SD_CFG_SCALE", "7")),
        sd_sampler=os.getenv("NARR_SD_SAMPLER", "DPM++ 2M Karras"),
        style_suffix=os.getenv(
            "NARR_STYLE_SUFFIX",
            "digital painting, historical illustration, warm muted earthy palette, painterly, cinematic lighting",
        ),
        target_fps=int(os.getenv("NARR_TARGET_FPS", "30")),
        xfade_duration=float(os.getenv("NARR_XFADE_DURATION", "0.5")),
    )
