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

Caso aparte: una esquina en blanco aislada (el resto del marco ya tiene
contenido, típico de escaneos de libro) no baja lo suficiente el `row_frac`/
`col_frac` de su fila/columna completa como para activar el recorte
rectangular. Ese caso se trata por separado: se analiza cada esquina con su
propio color (no el `border` combinado, que queda dominado por las otras 3
esquinas) y, si hay una región en blanco contigua a la esquina, se rellena
por inpainting (extrapolando el contenido vecino) en vez de recortar
—recortar movería contenido real del resto de esa fila/columna— y en vez de
repintarla de su propio color, que dejaría el parche intacto (ya es ese
color).
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_DIFF_THRESH = 32       # diferencia de color para contar un pixel como "contenido"
_CONTENT_FRAC = 0.18    # fracción mínima de contenido para que una línea NO sea margen
_MAX_CROP_FRAC = 0.42   # tope de recorte por lado

_CORNER_CONTENT_FRAC = 0.15  # fracción máx. de contenido en una fila/col de la esquina para seguir siendo "blanco"
_CORNER_MIN_FRAC = 0.04      # tamaño mínimo de esquina para molestarse en pintarla
_CORNER_MAX_FRAC = 0.30      # tamaño máx. de esquina a considerar
_CORNER_MAX_TOTAL_AREA_FRAC = 0.5  # tope combinado de las 4 esquinas


def _corner_colors(img):
    import numpy as np

    k = 8
    patches = {
        "tl": img[:k, :k].reshape(-1, 3),
        "tr": img[:k, -k:].reshape(-1, 3),
        "bl": img[-k:, :k].reshape(-1, 3),
        "br": img[-k:, -k:].reshape(-1, 3),
    }
    return {name: np.median(patch, axis=0) for name, patch in patches.items()}


def _corner_box(img, corner: str, color) -> tuple[int, int]:
    """Escanea desde una esquina hacia adentro y devuelve (dy, dx) del
    rectángulo contiguo a la esquina cuyo color coincide con `color`.

    Dos pasadas para no diluir el promedio con columnas/filas que quedan
    fuera del parche real: primero se estima el ancho del parche a partir de
    la fila más pegada a la esquina (`dx0`), luego se mide `dy` mirando solo
    esas columnas, y por último se remide `dx` mirando solo esas filas.
    """
    import numpy as np

    h, w = img.shape[:2]
    max_dy = int(h * _CORNER_MAX_FRAC)
    max_dx = int(w * _CORNER_MAX_FRAC)
    if max_dy < 1 or max_dx < 1:
        return 0, 0

    rows = slice(0, max_dy) if corner in ("tl", "tr") else slice(h - max_dy, h)
    cols = slice(0, max_dx) if corner in ("tl", "bl") else slice(w - max_dx, w)
    window = img[rows, cols]
    diff = np.abs(window.astype(np.int16) - color).sum(axis=2)
    blank = diff <= _DIFF_THRESH

    edge_row = blank[0] if corner in ("tl", "tr") else blank[-1]
    col_order = range(max_dx) if corner in ("tl", "bl") else range(max_dx - 1, -1, -1)
    dx0 = 0
    for j in col_order:
        if edge_row[j]:
            dx0 += 1
        else:
            break
    if dx0 == 0:
        return 0, 0

    probe_cols = slice(0, dx0) if corner in ("tl", "bl") else slice(max_dx - dx0, max_dx)
    row_order = range(max_dy) if corner in ("tl", "tr") else range(max_dy - 1, -1, -1)
    dy = 0
    for i in row_order:
        if blank[i, probe_cols].mean() >= 1 - _CORNER_CONTENT_FRAC:
            dy += 1
        else:
            break
    if dy == 0:
        return 0, 0

    probe_rows = slice(0, dy) if corner in ("tl", "tr") else slice(max_dy - dy, max_dy)
    dx = 0
    for j in col_order:
        if blank[probe_rows, j].mean() >= 1 - _CORNER_CONTENT_FRAC:
            dx += 1
        else:
            break

    if dy < h * _CORNER_MIN_FRAC or dx < w * _CORNER_MIN_FRAC:
        return 0, 0
    return dy, dx


def _paint_l_corners(img):
    """Detecta esquinas en blanco aisladas y las rellena por inpainting.

    Repintarlas de su propio color sería un no-op (ya son ese color); lo que
    hace falta es hacer desaparecer el parche extrapolando el contenido
    vecino, como si esa esquina nunca hubiera estado en blanco.
    """
    import cv2
    import numpy as np

    h, w = img.shape[:2]
    colors = _corner_colors(img)
    max_total_area = h * w * _CORNER_MAX_TOTAL_AREA_FRAC
    mask = np.zeros((h, w), np.uint8)
    masked_area = 0

    for corner in ("tl", "tr", "bl", "br"):
        dy, dx = _corner_box(img, corner, colors[corner])
        if dy == 0 or dx == 0:
            continue
        if masked_area + dy * dx > max_total_area:
            continue
        rows = slice(0, dy) if corner in ("tl", "tr") else slice(h - dy, h)
        cols = slice(0, dx) if corner in ("tl", "bl") else slice(w - dx, w)
        mask[rows, cols] = 255
        masked_area += dy * dx
        logger.info("Esquina en L detectada (%s): %dx%d, se rellena por inpainting", corner, dx, dy)

    if masked_area == 0:
        return img
    return cv2.inpaint(img, mask, 7, cv2.INPAINT_TELEA)


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
        result = _paint_l_corners(img)
        dest.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(dest), result)
        return dest

    cropped = _paint_l_corners(img[y0:y1, x0:x1])
    dest.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(dest), cropped)
    logger.info("Recortado marco de %s: %dx%d -> %dx%d", src.name, w, h, x1 - x0, y1 - y0)
    return dest
