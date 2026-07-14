"""Heurística ligera (sin ML) para decidir si un resultado de stock es
relevante, y para derivar una query de búsqueda a partir del prompt IA.

Mismo estilo que `_sfx_kind` en audio_bed.py: coincidencia de palabras clave,
nada de embeddings. Suficiente para descartar resultados obviamente
irrelevantes sin bloquear la investigación de medios para "cualquier video".
"""

import re

# Palabras de estilo/cámara que sobran en una búsqueda de stock real: describen
# cómo se renderiza la imagen IA, no qué contiene.
_STYLE_STOPWORDS = {
    "cinematic", "photorealistic", "dramatic", "wide", "shot", "close-up",
    "closeup", "low", "high", "angle", "lighting", "light", "atmosphere",
    "atmospheric", "render", "3d", "view", "digital", "painting",
    "illustration", "warm", "muted", "earthy", "palette", "painterly",
    "documentary", "natural", "history", "detail", "different", "composition",
}

# Conectores genéricos en inglés: no describen contenido, solo diluyen la
# búsqueda (motores de stock buscan mejor con 3-6 sustantivos/adjetivos que
# con una frase completa).
_CONNECTOR_STOPWORDS = {
    "the", "and", "with", "from", "toward", "towards", "into", "onto",
    "aimed", "over", "near", "that", "this", "these", "those", "for",
}

# Wikimedia Commons (CirrusSearch) trata varios términos como AND implícito:
# más de ~3-4 palabras de contenido casi siempre da 0 resultados aunque cada
# palabra por separado exista. Confirmado empíricamente contra la API real.
_MAX_QUERY_WORDS = 4
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


def relevance_score(query: str, candidate_text: str) -> float:
    """Solapamiento de palabras clave (0..1): cuántas palabras de la query
    aparecen en el título/tags del candidato."""
    query_words = _words(query) - _STYLE_STOPWORDS
    if not query_words:
        return 0.0
    candidate_words = _words(candidate_text)
    overlap = query_words & candidate_words
    return len(overlap) / len(query_words)
