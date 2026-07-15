"""Dirección de la mascota: decide QUÉ expresión/movimiento hace en cada momento
del video para que se sienta que está *presentando* —no un muñeco pegado—.

Es lógica pura (no toca imágenes ni ffmpeg). Toma la línea de tiempo de los
planos (con su texto de narración) y devuelve segmentos (inicio, fin, acción).
La expresión de cada plano se **infiere del contenido** de la narración (igual
que el perfil de movimiento infiere la energía de la cámara): si el texto habla
de peligro la mascota se asusta, si revela algo se sorprende, si pregunta
piensa, si da datos señala, etc. El compositor luego dibuja los sprites y,
dentro de los segmentos de "hablar", alterna a "idle" cuando la voz calla
(lip-sync por presencia de voz).

Acciones (el usuario las provee como carpetas/animaciones; ver README):
- talk      : hablando (boca en movimiento) — base mientras narra un plano
- idle      : quieta, respira/parpadea — pausas y relleno
- wave      : saluda — entrada del contenido
- walk      : camina DESPLAZÁNDOSE — entrada (entra a cuadro) y paseo entre planos
- point     : señala — datos, cifras, énfasis
- jump      : salta — planos de mucha energía / emoción
- celebrate : festeja — cierre / CTA
- scared    : asustada — peligro, amenaza, catástrofe
- surprised : sorprendida — revelación, giro, "no vas a creer"
- think     : pensativa — preguntas, misterio, "¿y si...?"
- sad       : triste — pérdida, muerte, tragedia
- laugh     : ríe — momento gracioso / ligero

Solo `talk` e `idle` son obligatorias. Cualquier acción opcional que falte cae
por una cadena de reemplazo hasta una que sí exista (p. ej. scared -> think ->
idle), así el video nunca se rompe por un sprite ausente.
"""

from dataclasses import dataclass

TALK = "talk"
IDLE = "idle"
WAVE = "wave"
WALK = "walk"
POINT = "point"
JUMP = "jump"
CELEBRATE = "celebrate"
SCARED = "scared"
SURPRISED = "surprised"
THINK = "think"
SAD = "sad"
LAUGH = "laugh"

REQUIRED_ACTIONS = (TALK, IDLE)
OPTIONAL_ACTIONS = (WAVE, WALK, POINT, JUMP, CELEBRATE, SCARED, SURPRISED, THINK, SAD, LAUGH)
ALL_ACTIONS = REQUIRED_ACTIONS + OPTIONAL_ACTIONS

_ONESHOT_SECONDS = 0.9   # gesto puntual (point/scared/surprised/...)
_ENTRANCE_SECONDS = 1.2  # la mascota entra caminando a cuadro

# Cadenas de reemplazo: si la acción ideal no está en la carpeta, se prueba la
# siguiente, hasta caer en una obligatoria (talk/idle) que siempre existe.
_FALLBACKS = {
    WAVE: (WAVE, TALK),
    WALK: (WALK, IDLE),
    POINT: (POINT, WAVE, TALK),
    JUMP: (JUMP, CELEBRATE, TALK),
    CELEBRATE: (CELEBRATE, JUMP, WAVE, TALK),
    SCARED: (SCARED, THINK, IDLE),
    SURPRISED: (SURPRISED, JUMP, POINT, TALK),
    THINK: (THINK, POINT, IDLE),
    SAD: (SAD, THINK, IDLE),
    LAUGH: (LAUGH, CELEBRATE, TALK),
}

# Palabras (sin acentos, minúsculas) que disparan cada expresión. El orden de
# este diccionario es el orden de prioridad al inferir (primera que coincide).
_EMOTION_WORDS = {
    SCARED: ("peligro", "terremot", "destru", "atac", "monstru", "miedo", "aterr",
             "huir", "escap", "catastrof", "derrumb", "amenaz", "horror", "guerra",
             "explos", "incendi", "tormenta", "veneno", "bestia"),
    SURPRISED: ("increible", "sorprend", "nadie sab", "de repente", "inesperad",
                "jamas", "nunca antes", "secreto", "revel", "descubr",
                "no vas a creer", "asombr", "resulta que", "de golpe"),
    SAD: ("murio", "muerte", "morir", "desaparec", "perdio", "tragedia", "triste",
          "adios", "ruina", "lloro", "llanto", "abandon", "soledad", "olvid",
          "el fin de", "ultimo dia"),
    THINK: ("imagina", "por que", "que pasaria", "pregunt", "misterio", "quiza",
            "tal vez", "y si ", "como es posible", "enigma", "acaso", "reflexi"),
    LAUGH: ("gracios", "jaja", "divertid", "chiste", "absurd", "ridicul", "comic",
            "risa"),
    POINT: ("metros", "kilometr", "millones", "miles de", "años", "siglo",
            "primero", "mas grande", "mas alto", "mas rapido", "record",
            "numero", "por ciento", "toneladas", "grados"),
}


@dataclass(frozen=True)
class PlanoBeat:
    """Lo que el director necesita de cada plano, ya con el offset de intro."""

    start: float
    end: float
    energetic: bool         # motion impact/energetic -> candidato a saltar
    text: str = ""          # narración del plano (para inferir la expresión)


@dataclass(frozen=True)
class MascotSegment:
    start: float
    end: float
    action: str
    variant: str = ""       # walk: "in" (entra a cuadro) | "pace" (paseo ida-vuelta)


def _strip(text: str) -> str:
    trans = str.maketrans("áéíóúüñ", "aeiouun")
    return text.lower().translate(trans)


def _resolve(action: str, available: set[str]) -> str | None:
    """Primera acción disponible en la cadena de reemplazo; None si ninguna."""
    for cand in _FALLBACKS.get(action, (action,)):
        if cand in available:
            return cand
    return None


def infer_expression(text: str, energetic: bool, available: set[str]) -> str | None:
    """Expresión a disparar al entrar a un plano según su narración.

    Devuelve la acción (ya resuelta a una disponible) o None si el plano no pide
    ningún gesto especial (se queda en 'talk')."""
    norm = _strip(text)
    for emotion, words in _EMOTION_WORDS.items():
        if any(w in norm for w in words):
            resolved = _resolve(emotion, available)
            if resolved is not None:
                return resolved
    if energetic:  # sin palabra clara pero con cámara energética -> salta
        return _resolve(JUMP, available)
    return None


def plan_mascot(
    beats: list[PlanoBeat],
    available: set[str],
    cta_start: float | None = None,
    cta_duration: float = 3.0,
) -> list[MascotSegment]:
    """Segmentos de acción de la mascota, en orden y sin huecos dentro de cada
    plano (el compositor rellena el resto con idle)."""
    if not beats:
        return []
    segs: list[MascotSegment] = []

    def oneshot(start: float, end: float, action: str | None,
                seconds: float = _ONESHOT_SECONDS, variant: str = "") -> float:
        """Coloca un gesto puntual al inicio si `action` existe y cabe.
        Devuelve el tiempo donde sigue el 'talk'."""
        if action and action in available:
            gesture_end = min(start + seconds, end)
            if gesture_end > start:
                segs.append(MascotSegment(start, gesture_end, action, variant))
                return gesture_end
        return start

    walk = WALK if WALK in available else None  # sin walk real no hay traslado
    for i, b in enumerate(beats):
        t = b.start
        if i == 0:
            # Entra caminando a cuadro y luego saluda: presentación en toda regla.
            t = oneshot(t, b.end, walk, _ENTRANCE_SECONDS, "in")
            t = oneshot(t, b.end, _resolve(WAVE, available))
        else:
            expr = infer_expression(b.text, b.energetic, available)
            if expr is not None:
                t = oneshot(t, b.end, expr)
            elif i % 2 == 0:
                # plano tranquilo sin emoción clara -> pasea (ida y vuelta) para
                # no quedarse clavada; si no hay walk, sigue de largo a 'talk'.
                t = oneshot(t, b.end, walk, variant="pace")
        if t < b.end:
            segs.append(MascotSegment(t, b.end, TALK))

    # Cierre / CTA: festeja.
    if cta_start is not None:
        action = _resolve(CELEBRATE, available) or IDLE
        segs.append(MascotSegment(cta_start, cta_start + cta_duration, action))
    return segs


def segment_at(segments: list[MascotSegment], t: float) -> MascotSegment | None:
    """Segmento activo en el instante t (None si no hay)."""
    for s in segments:
        if s.start <= t < s.end:
            return s
    return None


def action_at(segments: list[MascotSegment], t: float) -> str:
    """Acción activa en el instante t (idle si no hay segmento)."""
    s = segment_at(segments, t)
    return s.action if s is not None else IDLE
