"""Composición de dependencias: instancia adaptadores y los provee a los casos de uso."""

from functools import cached_property

from illustrated_narrator.adapters.audio.audio_bed import AudioBedBuilder
from illustrated_narrator.adapters.images.automatic1111_adapter import Automatic1111ImageAdapter
from illustrated_narrator.adapters.media.freesound_adapter import FreesoundAdapter
from illustrated_narrator.adapters.media.pexels_adapter import PexelsImageAdapter
from illustrated_narrator.adapters.media.pexels_video_adapter import PexelsVideoAdapter
from illustrated_narrator.adapters.media.wikimedia_adapter import WikimediaCommonsAdapter
from illustrated_narrator.adapters.transcription.faster_whisper_adapter import FasterWhisperTranscriber
from illustrated_narrator.adapters.video.ffmpeg_assembler import FFmpegAssembler
from illustrated_narrator.domain.use_cases.generate_narration_video import GenerateNarrationVideo
from illustrated_narrator.domain.use_cases.generate_plano_images import GeneratePlanoImages
from illustrated_narrator.domain.use_cases.research_audio_assets import ResearchAudioAssets
from illustrated_narrator.domain.use_cases.research_plano_media import ResearchPlanoMedia
from illustrated_narrator.infrastructure.config import Settings
from illustrated_narrator.infrastructure.ffmpeg_locator import resolve_ffmpeg
from illustrated_narrator.ports.image_generator import ImageGeneratorPort
from illustrated_narrator.ports.stock_audio import StockAudioPort
from illustrated_narrator.ports.stock_media import StockImagePort
from illustrated_narrator.ports.transcription import TranscriptionPort
from illustrated_narrator.ports.video_assembler import VideoAssemblerPort


class Container:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @cached_property
    def canvas(self) -> tuple[int, int]:
        return (1080, 1920) if self.settings.vertical else (1920, 1080)

    @cached_property
    def ffmpeg_path(self) -> str:
        return resolve_ffmpeg(self.settings.ffmpeg_path)

    @cached_property
    def image_generator(self) -> ImageGeneratorPort:
        if self.settings.image_backend == "placeholder":
            from illustrated_narrator.adapters.images.placeholder_adapter import (
                PlaceholderImageAdapter,
            )

            return PlaceholderImageAdapter()
        return Automatic1111ImageAdapter(
            self.settings.a1111_base_url, checkpoint=self.settings.sd_checkpoint
        )

    @cached_property
    def transcriber(self) -> TranscriptionPort:
        s = self.settings
        return FasterWhisperTranscriber(
            model_size=s.whisper_model, cpu_threads=s.whisper_cpu_threads
        )

    @cached_property
    def depth_estimator(self):
        """Estimador de profundidad para parallax 2.5D; None = solo Ken Burns.
        Solo el modelo real (ONNX); sin él se cae a Ken Burns, no a profundidad falsa."""
        if not self.settings.enable_parallax:
            return None
        from illustrated_narrator.adapters.depth.onnx_depth import OnnxDepthEstimator

        onnx = OnnxDepthEstimator(self.settings.depth_model_path)
        return onnx if onnx.is_available() else None

    @cached_property
    def video_assembler(self) -> VideoAssemblerPort:
        return FFmpegAssembler(
            ffmpeg_path=self.ffmpeg_path,
            encoder=self.settings.video_encoder,
            fps=self.settings.target_fps,
            canvas=self.canvas,
            depth_estimator=self.depth_estimator,
            style_mode=self.settings.style_mode,
            process_voice=self.settings.process_voice,
        )

    @cached_property
    def audio_bed_builder(self) -> AudioBedBuilder | None:
        if not self.settings.enable_audio_bed:
            return None
        return AudioBedBuilder(
            ffmpeg_path=self.ffmpeg_path, music_volume=self.settings.music_volume
        )

    @cached_property
    def _pexels_adapter(self) -> PexelsImageAdapter:
        return PexelsImageAdapter(self.settings.pexels_api_key)

    @cached_property
    def _pexels_video_adapter(self) -> PexelsVideoAdapter | None:
        if not self.settings.enable_video_broll:
            return None
        return PexelsVideoAdapter(self.settings.pexels_api_key, vertical=self.settings.vertical)

    @cached_property
    def _wikimedia_adapter(self) -> WikimediaCommonsAdapter:
        return WikimediaCommonsAdapter()

    @cached_property
    def _freesound_adapter(self) -> FreesoundAdapter:
        return FreesoundAdapter(self.settings.freesound_api_key)

    @cached_property
    def stock_image_sources_default(self) -> list[StockImagePort]:
        """Orden por defecto: stock general (fotos + B-roll de video) primero,
        archivo como respaldo. El video compite por relevancia igual que las
        fotos — no hay prioridad fija entre ambos."""
        candidates = [self._pexels_adapter, self._pexels_video_adapter, self._wikimedia_adapter]
        return [c for c in candidates if c is not None and c.is_available()]

    @cached_property
    def stock_image_sources_historico(self) -> list[StockImagePort]:
        """Planos archivo_historico: archivo público primero, stock de respaldo."""
        candidates = [self._wikimedia_adapter, self._pexels_adapter, self._pexels_video_adapter]
        return [c for c in candidates if c is not None and c.is_available()]

    @cached_property
    def stock_audio_source(self) -> StockAudioPort | None:
        return self._freesound_adapter if self._freesound_adapter.is_available() else None

    @cached_property
    def research_plano_media(self) -> ResearchPlanoMedia | None:
        # Consistencia de estilo: en modo "ilustracion" se generan TODAS las
        # imágenes con IA (mismo style_suffix) y no se mezclan fotos reales.
        if not self.settings.enable_media_research or self.settings.style_mode == "ilustracion":
            return None
        return ResearchPlanoMedia(
            sources_default=self.stock_image_sources_default,
            sources_historico=self.stock_image_sources_historico,
            candidates_per_shot=self.settings.media_candidates_per_shot,
            min_score=self.settings.media_relevance_min_score,
        )

    @cached_property
    def research_audio_assets(self) -> ResearchAudioAssets | None:
        if not self.settings.enable_media_research:
            return None
        return ResearchAudioAssets(self.stock_audio_source)

    @cached_property
    def generate_plano_images(self) -> GeneratePlanoImages:
        s = self.settings
        # En vertical las imágenes se generan altas (el lienzo lo pide)
        width, height = (s.sd_width, s.sd_height)
        if s.vertical:
            width, height = (s.sd_height, s.sd_width)
        return GeneratePlanoImages(
            self.image_generator,
            style_suffix=s.style_suffix,
            negative_prompt=s.sd_negative_prompt,
            steps=s.sd_steps,
            cfg_scale=s.sd_cfg_scale,
            sampler_name=s.sd_sampler,
            width=width,
            height=height,
        )

    @cached_property
    def generate_narration_video(self) -> GenerateNarrationVideo:
        from illustrated_narrator.domain.services.brand_palette import hex_to_ass_color

        return GenerateNarrationVideo(
            self.transcriber,
            self.generate_plano_images,
            self.video_assembler,
            xfade_duration=self.settings.xfade_duration,
            audio_bed_builder=self.audio_bed_builder,
            canvas=self.canvas,
            cta_text=self.settings.cta_text,
            cta_duration=self.settings.cta_duration,
            research_plano_media=self.research_plano_media,
            research_audio_assets=self.research_audio_assets,
            brand_name=self.settings.brand_name,
            brand_intro_duration=self.settings.brand_intro_duration,
            accent_color_ass=hex_to_ass_color(self.settings.brand_accent_color),
        )
