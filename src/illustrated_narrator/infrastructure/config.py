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
    image_backend: str  # "a1111" | "placeholder"
    a1111_base_url: str
    sd_checkpoint: str | None
    sd_negative_prompt: str
    sd_steps: int
    sd_cfg_scale: float
    sd_sampler: str
    sd_width: int
    sd_height: int
    style_suffix: str
    target_fps: int
    xfade_duration: float
    vertical: bool
    music_volume: float
    enable_audio_bed: bool
    cta_text: str | None
    cta_duration: float


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
        image_backend=os.getenv("NARR_IMAGE_BACKEND", "a1111").strip().lower(),
        a1111_base_url=os.getenv("NARR_A1111_BASE_URL", "http://127.0.0.1:7860"),
        sd_checkpoint=os.getenv("NARR_SD_CHECKPOINT", "").strip() or None,
        sd_negative_prompt=os.getenv(
            "NARR_SD_NEGATIVE_PROMPT", "blurry, low quality, deformed, watermark, text"
        ),
        sd_steps=int(os.getenv("NARR_SD_STEPS", "20")),
        sd_cfg_scale=float(os.getenv("NARR_SD_CFG_SCALE", "7")),
        sd_sampler=os.getenv("NARR_SD_SAMPLER", "DPM++ 2M Karras"),
        sd_width=int(os.getenv("NARR_SD_WIDTH", "768")),
        sd_height=int(os.getenv("NARR_SD_HEIGHT", "448")),
        style_suffix=os.getenv(
            "NARR_STYLE_SUFFIX",
            "digital painting, historical illustration, warm muted earthy palette, painterly, cinematic lighting",
        ),
        target_fps=int(os.getenv("NARR_TARGET_FPS", "30")),
        xfade_duration=float(os.getenv("NARR_XFADE_DURATION", "0.28")),
        vertical=os.getenv("NARR_VERTICAL", "").strip() in ("1", "true", "si", "sí"),
        music_volume=float(os.getenv("NARR_MUSIC_VOLUME", "0.22")),
        enable_audio_bed=os.getenv("NARR_AUDIO_BED", "1").strip() not in ("0", "false", "no"),
        cta_text=os.getenv("NARR_CTA_TEXT", "SÍGUEME PARA MÁS HISTORIAS").strip() or None,
        cta_duration=float(os.getenv("NARR_CTA_DURATION", "3.0")),
    )
