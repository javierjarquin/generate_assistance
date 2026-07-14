"""Limpieza de imágenes antes de renderizar: recorta marcos/bordes.

Muchas imágenes (escaneos de cuadros, láminas de libro) traen un margen sólido
—blanco, negro o gris— a veces con texto impreso disperso. Ese marco arruina el
plano (sobre todo el gancho) y confunde al parallax.

Detección robusta: se toma el color del borde de las esquinas y se marca como
"contenido" cada pixel que difiere de ese color. Una fila/columna es margen si
tiene poca fracción de contenido (así el texto disperso del margen se sigue
tratando como margen, no como contenido). Se recorta al recuadro de contenido.

Conservador: nunca recorta más de `MAX_CROP_FRAC` por lado y descarta recortes
sospechosamente grandes.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_DIFF_THRESH = 32       # diferencia de color para contar un pixel como "contenido"
_CONTENT_FRAC = 0.18    # fracción mínima de contenido para que una línea NO sea margen
_MAX_CROP_FRAC = 0.42   # tope de recorte por lado


def clean_image(src: Path, dest: Path) -> Path:
    import cv2
    import numpy as np

    img = cv2.imread(str(src), cv2.IMREAD_COLOR)
    if img is None:
        return src
    h, w = img.shape[:2]

    # Color del borde = mediana de las 4 esquinas (parches 8x8)
    k = 8
    corners = np.concatenate([
        img[:k, :k].reshape(-1, 3), img[:k, -k:].reshape(-1, 3),
        img[-k:, :k].reshape(-1, 3), img[-k:, -k:].reshape(-1, 3),
    ])
    border = np.median(corners, axis=0)

    diff = np.abs(img.astype(np.int16) - border).sum(axis=2)  # HxW
    content = diff > _DIFF_THRESH
    row_frac = content.mean(axis=1)
    col_frac = content.mean(axis=0)

    def _scan(frac, limit):
        i = 0
        while i < limit and frac[i] < _CONTENT_FRAC:
            i += 1
        return i

    top = _scan(row_frac, int(h * _MAX_CROP_FRAC))
    bottom = _scan(row_frac[::-1], int(h * _MAX_CROP_FRAC))
    left = _scan(col_frac, int(w * _MAX_CROP_FRAC))
    right = _scan(col_frac[::-1], int(w * _MAX_CROP_FRAC))

    y0, y1, x0, x1 = top, h - bottom, left, w - right
    if (top + bottom + left + right == 0) or (y1 - y0 < h * 0.35) or (x1 - x0 < w * 0.35):
        if dest != src:
            dest.parent.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(str(dest), img)
        return dest

    cropped = img[y0:y1, x0:x1]
    dest.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(dest), cropped)
    logger.info("Recortado marco de %s: %dx%d -> %dx%d", src.name, w, h, x1 - x0, y1 - y0)
    return dest
