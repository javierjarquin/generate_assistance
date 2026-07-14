from dataclasses import dataclass, field

from illustrated_narrator.domain.entities.plano import Plano


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
