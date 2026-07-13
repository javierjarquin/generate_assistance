from dataclasses import dataclass, field
from enum import Enum


class VisualTipo(str, Enum):
    IMAGEN_IA = "imagen_ia"
    VIDEO_STOCK = "video_stock"
    ANIMACION_3D = "animacion_3d"
    MAPA_ANIMADO = "mapa_animado"
    GRAFICO_MOVIMIENTO = "grafico_movimiento"
    CARTEL_TEXTO = "cartel_texto"
    ARCHIVO_HISTORICO = "archivo_historico"


class PlanoEstado(str, Enum):
    PENDIENTE = "pendiente"
    ALINEADO = "alineado"
    IMAGEN_GENERADA = "imagen_generada"
    CLIP_LISTO = "clip_listo"
    FALLIDO = "fallido"


@dataclass(frozen=True)
class VisualSpec:
    tipo: VisualTipo
    descripcion: str = ""
    prompt_ia: str = ""
    nota: str | None = None
    # Overlay animado del clip: niebla|polvo|lluvia|burbujas|fuego (parpadeo)
    overlay: str | None = None
    # Sacudida de cámara (terremotos, impactos)
    shake: bool = False


@dataclass(frozen=True)
class AudioSpec:
    musica: str | None = None
    sfx: str | None = None


@dataclass
class Plano:
    """Un plano del guion: narracion + su visual, texto en pantalla y audio.

    inicio_aprox/duracion_seg_estimada vienen del guion de entrada (estimados a
    150 palabras/min) y son solo referencia de planeacion. inicio_real_seg/
    fin_real_seg los llena AlignScriptToAudio a partir del audio real grabado
    -- son los que de verdad se usan para renderizar.
    """

    id: str
    seccion: str
    narracion: str
    visual: VisualSpec
    texto_en_pantalla: str | None = None
    audio: AudioSpec = field(default_factory=AudioSpec)
    inicio_aprox: str | None = None
    duracion_seg_estimada: float | None = None

    inicio_real_seg: float | None = None
    fin_real_seg: float | None = None
    estado: PlanoEstado = PlanoEstado.PENDIENTE
    imagen_path: str | None = None
    clip_path: str | None = None

    @property
    def duracion_real_seg(self) -> float | None:
        if self.inicio_real_seg is None or self.fin_real_seg is None:
            return None
        return self.fin_real_seg - self.inicio_real_seg
