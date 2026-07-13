"""Composición de dependencias: instancia adaptadores y los provee a los casos de uso."""

from functools import cached_property

from illustrated_narrator.adapters.images.automatic1111_adapter import Automatic1111ImageAdapter
from illustrated_narrator.adapters.transcription.faster_whisper_adapter import FasterWhisperTranscriber
from illustrated_narrator.adapters.video.ffmpeg_assembler import FFmpegAssembler
from illustrated_narrator.domain.use_cases.generate_narration_video import GenerateNarrationVideo
from illustrated_narrator.domain.use_cases.generate_plano_images import GeneratePlanoImages
from illustrated_narrator.infrastructure.config import Settings
from illustrated_narrator.infrastructure.ffmpeg_locator import resolve_ffmpeg
from illustrated_narrator.ports.image_generator import ImageGeneratorPort
from illustrated_narrator.ports.transcription import TranscriptionPort
from illustrated_narrator.ports.video_assembler import VideoAssemblerPort


class Container:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @cached_property
    def ffmpeg_path(self) -> str:
        return resolve_ffmpeg(self.settings.ffmpeg_path)

    @cached_property
    def image_generator(self) -> ImageGeneratorPort:
        return Automatic1111ImageAdapter(self.settings.a1111_base_url)

    @cached_property
    def transcriber(self) -> TranscriptionPort:
        s = self.settings
        return FasterWhisperTranscriber(
            model_size=s.whisper_model, cpu_threads=s.whisper_cpu_threads
        )

    @cached_property
    def video_assembler(self) -> VideoAssemblerPort:
        return FFmpegAssembler(
            ffmpeg_path=self.ffmpeg_path, encoder=self.settings.video_encoder, fps=self.settings.target_fps
        )

    @cached_property
    def generate_plano_images(self) -> GeneratePlanoImages:
        s = self.settings
        return GeneratePlanoImages(
            self.image_generator,
            style_suffix=s.style_suffix,
            negative_prompt=s.sd_negative_prompt,
            steps=s.sd_steps,
            cfg_scale=s.sd_cfg_scale,
            sampler_name=s.sd_sampler,
        )

    @cached_property
    def generate_narration_video(self) -> GenerateNarrationVideo:
        return GenerateNarrationVideo(
            self.transcriber,
            self.generate_plano_images,
            self.video_assembler,
            xfade_duration=self.settings.xfade_duration,
        )
