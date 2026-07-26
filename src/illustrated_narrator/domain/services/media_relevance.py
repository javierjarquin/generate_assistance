"""Heurística ligera (sin ML) para decidir si un resultado de stock es
relevante, y para derivar una query de búsqueda a partir del prompt IA.

Mismo estilo que `_sfx_kind` en audio_bed.py: coincidencia de palabras clave,
nada de embeddings. Suficiente para descartar resultados obviamente
irrelevantes sin bloquear la investigación de medios para "cualquier video".
"""

import difflib
import re

# Palabras de estilo/cámara que sobran en una búsqueda de stock real: describen
# cómo se renderiza la imagen IA, no qué contiene.
_STYLE_STOPWORDS = {
    "cinematic", "photorealistic", "dramatic", "wide", "shot", "close-up",
    "closeup", "low", "high", "angle", "lighting", "light", "atmosphere",
    "atmospheric", "render", "3d", "view", "digital", "painting",
    "illustration", "warm", "muted", "earthy", "palette", "painterly",
    "documentary", "natural", "history", "detail", "different", "composition",
    # Instrucciones de encuadre/formato, no contenido -- colarse en la query
    # sólo diluye la búsqueda y nunca describe qué hay en la imagen (visto en
    # una corrida real: "vertical" quedó como palabra de la query de un plano
    # de Yucatan y no aportó nada a la relevancia, solo bajó el umbral).
    "vertical", "horizontal", "portrait", "landscape", "format", "frame",
    "framing", "aspect", "ratio",
}

# Conectores genéricos en inglés: no describen contenido, solo diluyen la
# búsqueda (motores de stock buscan mejor con 3-6 sustantivos/adjetivos que
# con una frase completa).
_CONNECTOR_STOPWORDS = {
    "the", "and", "with", "from", "toward", "towards", "into", "onto",
    "aimed", "over", "near", "that", "this", "these", "those", "for",
}

# Subido de 4 a 6: el tope de 4 era en realidad una limitación de Wikimedia
# Commons (CirrusSearch trata varios términos como AND implícito), pero
# wikimedia_adapter.py YA tiene su propio acortador progresivo interno
# (prueba con la query completa y recorta de a una palabra si no hay
# resultados) -- el tope acá de nada servía para Wikimedia y solo le quitaba
# especificidad a Pexels, que sí maneja bien queries más largas y ricas (su
# búsqueda es semántica, no AND literal). Más palabras = más contexto de la
# ESCENA puntual, no solo el tema general.
_MAX_QUERY_WORDS = 6
_WORD_RE = re.compile(r"[a-záéíóúñ]+", re.IGNORECASE)


def _words(text: str) -> set[str]:
    return {w.lower() for w in _WORD_RE.findall(text) if len(w) > 2}


def _content_words(text: str) -> list[str]:
    return [
        w for w in _WORD_RE.findall(text)
        if len(w) > 2 and w.lower() not in _STYLE_STOPWORDS
        and w.lower() not in _CONNECTOR_STOPWORDS
    ]


def derive_query(prompt_ia: str, descripcion: str, override: str | None = None) -> str:
    """Query de búsqueda para stock a partir del guion: los primeros
    sustantivos/adjetivos de contenido de `prompt_ia` (sin conectores ni
    palabras de estilo), acotada para que un motor de stock la matchee bien.
    `override` (visual.busqueda_medios) siempre gana si el autor lo dio."""
    if override and override.strip():
        return override.strip()
    for source in (prompt_ia, descripcion):
        kept = _content_words(source or "")[:_MAX_QUERY_WORDS]
        if kept:
            return " ".join(kept)
    return (descripcion or prompt_ia or "").strip()


# Similitud mínima (difflib, 0..1) para contar dos palabras como "la misma"
# aunque no sean idénticas letra por letra. Wikimedia Commons tiene muchos
# títulos en portugués/alemán/latín científico frente a una query en inglés
# (derivada del prompt IA) -- ej. "tyrannosaurus" vs "tiranossauro" da 0.72,
# "meteorito" vs "meteor" da 0.80. Un match exacto exigía coincidencia
# literal y descartaba resultados claramente relevantes (confirmado contra
# una corrida real: 53/101 shots tenían candidatos descargados pero solo 8
# pasaban el umbral).
_FUZZY_MIN_RATIO = 0.70


def relevance_score(query: str, candidate_text: str) -> float:
    """Fracción (0..1) de palabras de la query que aparecen -exacta o
    aproximadamente (variantes de idioma/ortografía)- en el título/tags del
    candidato."""
    query_words = _words(query) - _STYLE_STOPWORDS
    if not query_words:
        return 0.0
    candidate_words = _words(candidate_text)
    if not candidate_words:
        return 0.0
    hits = 0
    for q in query_words:
        if q in candidate_words:
            hits += 1
            continue
        best = max(
            (difflib.SequenceMatcher(None, q, c).ratio() for c in candidate_words),
            default=0.0,
        )
        if best >= _FUZZY_MIN_RATIO:
            hits += 1
    return hits / len(query_words)
