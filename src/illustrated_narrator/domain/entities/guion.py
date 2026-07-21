from dataclasses import dataclass, field

from illustrated_narrator.domain.entities.plano import Plano


@dataclass(frozen=True)
class MascotaConfig:
    """Config de mascota declarada en el guion (meta.mascota).

    Todo es opcional: lo que no se declare aquí lo rellena la config de entorno
    (NARR_MASCOTA_*). Lo que SÍ se declara manda sobre el entorno — el guion es
    la fuente de verdad del video.
    """

    modo: str | None = None        # voz | mascota
    ruta: str | None = None        # carpeta de sprites (relativa a projects/<slug>/)
    pos: str | None = None         # bottom-right | bottom-left | bottom-center
    alto: float | None = None      # alto de la mascota como fracción del video
    fps: int | None = None         # fps de la animación
    umbral_voz: float | None = None  # sensibilidad del lip-sync (0-1)


@dataclass(frozen=True)
class GuionMeta:
    serie: str = ""
    capitulo: int = 0
    titulo: str = ""
    subtitulo: str | None = None
    idioma: str = "es-MX"
    # Gancho de tensión que se muestra en 0-3s (una pregunta/promesa que engancha,
    # no solo el tema). Si falta, se usa el título.
    gancho: str | None = None
    # Mascota que presenta el video. None = manda el entorno (NARR_NARRACION...).
    mascota: MascotaConfig | None = None


@dataclass(frozen=True)
class Guion:
    """El guion completo: metadata de la serie + los planos en orden.

    La narracion completa esperada en el audio es la concatenacion en orden
    de planos[].narracion -- es el texto conocido contra el que se alinea la
    grabacion real (ver AlignScriptToAudio).
    """

    meta: GuionMeta
    planos: list[Plano] = field(default_factory=list)

    def texto_completo(self) -> str:
        return " ".join(p.narracion for p in self.planos)
