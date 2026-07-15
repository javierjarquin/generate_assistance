from pathlib import Path

import pytest

np = pytest.importorskip("numpy")
cv2 = pytest.importorskip("cv2")

from illustrated_narrator.adapters.video.image_cleaner import clean_image


def test_crops_uniform_white_border(tmp_path: Path) -> None:
    # imagen 200x200 con contenido ruidoso en el centro 100x100 y marco blanco
    img = np.full((200, 200, 3), 255, np.uint8)
    img[50:150, 50:150] = np.random.randint(0, 200, (100, 100, 3), np.uint8)
    src = tmp_path / "bordered.png"
    cv2.imwrite(str(src), img)

    out = clean_image(src, tmp_path / "clean.png")
    result = cv2.imread(str(out))
    h, w = result.shape[:2]
    # el marco blanco se recortó (queda ~100x100, no 200x200)
    assert h < 180 and w < 180
    assert h >= 90 and w >= 90


def test_no_border_left_untouched(tmp_path: Path) -> None:
    img = np.random.randint(0, 255, (200, 200, 3), np.uint8)
    src = tmp_path / "full.png"
    cv2.imwrite(str(src), img)

    out = clean_image(src, tmp_path / "clean.png")
    result = cv2.imread(str(out))
    assert result.shape[:2] == (200, 200)


def test_paints_l_shaped_corner(tmp_path: Path) -> None:
    # contenido ruidoso en toda la imagen EXCEPTO una esquina superior derecha
    # blanca — el resto de esa fila/columna sí tiene contenido, así que el
    # recorte rectangular estándar (row_frac/col_frac de línea completa) no
    # debe activarse; el recorte fino por esquina sí debe neutralizarla.
    img = np.random.randint(0, 200, (200, 200, 3), np.uint8)
    img[:50, 150:] = 255
    src = tmp_path / "lcorner.png"
    cv2.imwrite(str(src), img)

    out = clean_image(src, tmp_path / "clean.png")
    result = cv2.imread(str(out))
    assert result.shape[:2] == (200, 200)  # no se recorta, se rellena in situ
    # la esquina ya no es un bloque blanco uniforme (se rellenó por inpainting
    # extrapolando el contenido vecino en vez de dejarla intacta)
    corner = result[:50, 150:]
    assert not (corner == 255).all()
    # el resto de la imagen, lejos de la esquina, no fue tocado
    untouched = img[100:150, 0:50]
    assert (result[100:150, 0:50] == untouched).all()


def test_huge_crop_rejected(tmp_path: Path) -> None:
    # casi toda uniforme con un puntito: no debe recortar al punto
    img = np.full((200, 200, 3), 128, np.uint8)
    img[100, 100] = (0, 255, 0)
    src = tmp_path / "flat.png"
    cv2.imwrite(str(src), img)

    out = clean_image(src, tmp_path / "clean.png")
    result = cv2.imread(str(out))
    # no colapsó a casi nada
    assert result.shape[0] >= 200 * 0.4 and result.shape[1] >= 200 * 0.4
