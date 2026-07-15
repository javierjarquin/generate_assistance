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
    brand_name: str | None
    brand_accent_color: str
    brand_intro_duration: float
    brand_logo_path: Path | None
    enable_media_research: bool
    enable_video_broll: bool
    pexels_api_key: str | None
    freesound_api_key: str | None
    media_candidates_per_shot: int
    media_relevance_min_score: float
    # Parallax 2.5D
    enable_parallax: bool
    depth_model_path: Path
    # Consistencia de estilo: "auto" | "ilustracion" | "realista" | "unificado"
    style_mode: str
    process_voice: bool


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
        brand_name=os.getenv("NARR_BRAND_NAME", "").strip() or None,
        brand_accent_color=os.getenv("NARR_BRAND_ACCENT_COLOR", "#FFE800").strip() or "#FFE800",
        brand_intro_duration=float(os.getenv("NARR_BRAND_INTRO_DURATION", "2.0")),
        brand_logo_path=(
            Path(os.getenv("NARR_BRAND_LOGO_PATH", "").strip())
            if os.getenv("NARR_BRAND_LOGO_PATH", "").strip()
            else None
        ),
        enable_media_research=os.getenv("NARR_ENABLE_MEDIA_RESEARCH", "1").strip()
        not in ("0", "false", "no"),
        enable_video_broll=os.getenv("NARR_MEDIA_ENABLE_VIDEO", "1").strip()
        not in ("0", "false", "no"),
        pexels_api_key=os.getenv("NARR_PEXELS_API_KEY", "").strip() or None,
        freesound_api_key=os.getenv("NARR_FREESOUND_API_KEY", "").strip() or None,
        media_candidates_per_shot=int(os.getenv("NARR_MEDIA_CANDIDATES_PER_SHOT", "3")),
        media_relevance_min_score=float(os.getenv("NARR_MEDIA_RELEVANCE_MIN_SCORE", "0.35")),
        enable_parallax=os.getenv("NARR_PARALLAX", "1").strip() not in ("0", "false", "no"),
        depth_model_path=Path(
            os.getenv("NARR_DEPTH_MODEL", _PROJECT_ROOT / "models" / "depth_anything_v2_vits.onnx")
        ),
        style_mode=os.getenv("NARR_STYLE_MODE", "auto").strip().lower(),
        process_voice=os.getenv("NARR_VOICE_PROCESSING", "1").strip() not in ("0", "false", "no"),
    )
