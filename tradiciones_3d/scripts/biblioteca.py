"""Biblioteca de modelos 3D del nicho de tradiciones (30/10/2026): estilo juguete.

    C:\\illustrated-narrator\\.venv\\Scripts\\python.exe tradiciones_3d\\scripts\\biblioteca.py

Baja los paquetes de Kenney (https://kenney.nl, licencia CC0: se pueden usar y
redistribuir sin pedir permiso), copia a public/modelos/<paquete>/ solo los modelos de
ELEGIDOS con su textura, y escribe public/modelos/indice.json, que es lo que lee el bot
(instruccion_tradiciones) para decirle a Claude qué hay. Para agregar un modelo:
súmalo a ELEGIDOS y vuelve a correr esto.

Javier escogió este estilo (juguete, low-poly) sobre el realista de Poly Haven.
Lo muy mexicano (calaverita, pan de muerto, piñata, rosca) no existe gratis en
ningún lado: eso se hace por código en Objetos.tsx.
"""

import json
import re
import sys
import zipfile
from pathlib import Path

import requests

AQUI = Path(__file__).resolve().parents[1]
# En public/ para que Remotion los sirva con staticFile("modelos/...").
MODELOS = AQUI / "public" / "modelos"
CACHE = AQUI / ".cache"
NAVEGADOR = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                           "Chrome/130.0 Safari/537.36"}

# paquete de Kenney -> {modelo: qué es, en español}
ELEGIDOS = {
    "graveyard-kit": {
        "altar-wood": "altar o mesa de madera", "altar-stone": "altar de piedra", "candle": "vela",
        "candle-multiple": "grupo de velas", "character-skeleton": "esqueleto de pie", "coffin": "ataúd",
        "coffin-old": "ataúd viejo", "cross": "cruz de piedra", "cross-wood": "cruz de madera",
        "detail-bowl": "cuenco", "detail-chalice": "cáliz", "detail-plate": "plato",
        "fire-basket": "brasero con fuego", "grave": "tumba de tierra", "gravestone-cross": "lápida con cruz",
        "gravestone-round": "lápida redonda", "gravestone-decorative": "lápida adornada",
        "lantern-candle": "farol con vela", "lantern-glass": "farol de vidrio", "pumpkin": "calabaza",
        "pumpkin-carved": "calabaza tallada", "urn-round": "urna", "shovel": "pala", "pine": "pino",
        "iron-fence": "reja de fierro", "crypt-small": "capillita de panteón", "lightpost-single": "farol de calle",
        "bench": "banca", "hay-bale": "paca de paja", "trunk": "tronco", "rocks": "piedras",
    },
    "food-kit": {
        "bread": "pan", "loaf-round": "pan redondo", "loaf": "pan alargado", "croissant": "cuerno de pan",
        "corn": "elote", "pumpkin": "calabaza de comer", "pot": "olla", "pot-stew": "olla con guiso (ponche, pozole)",
        "bowl": "tazón", "bowl-soup": "plato hondo con caldo", "mug": "jarro", "cup": "taza", "cup-coffee": "taza de café",
        "glass": "vaso", "plate": "plato", "mortar-pestle": "molcajete (mortero)", "taco": "taco", "tomato": "jitomate",
        "onion": "cebolla", "paprika": "chile morrón", "avocado": "aguacate", "orange": "naranja", "apple": "manzana",
        "banana": "plátano", "coconut": "coco", "watermelon": "sandía", "pineapple": "piña", "grapes": "uvas",
        "lemon": "limón", "cake": "pastel", "cake-birthday": "pastel de cumpleaños", "cookie": "galleta",
        "donut": "dona", "chocolate": "tableta de chocolate", "honey": "miel", "egg": "huevo",
        "egg-cooked": "huevo estrellado", "fish": "pescado", "meat-cooked": "carne asada", "turkey": "guajolote asado",
        "lollypop": "paleta de dulce", "ice-cream": "helado", "rollingPin": "rodillo", "steamer": "vaporera",
        "soda-bottle": "botella de refresco", "cutting-board": "tabla de picar", "frying-pan": "sartén",
    },
    "holiday-kit": {
        "tree-decorated": "árbol de Navidad", "tree-decorated-snow": "árbol de Navidad con nieve",
        "present-a-cube": "regalo cuadrado", "present-b-round": "regalo redondo", "present-a-rectangle": "regalo largo",
        "wreath-decorated": "corona navideña", "lantern": "farol", "lantern-hanging": "farol colgante",
        "lights-colored": "serie de luces", "candy-cane-red": "bastón de caramelo", "gingerbread-man": "galleta de jengibre",
        "sock-red": "calcetín navideño", "reindeer": "reno", "snowman": "muñeco de nieve", "sled": "trineo",
        "hanukkah-menorah-candles": "candelabro con velas", "snowflake-a": "copo de nieve",
    },
    "survival-kit": {
        "campfire-pit": "fogata", "campfire-stand": "fogata con olla colgada", "barrel": "barril", "bucket": "cubeta",
        "box": "caja de madera", "chest": "cofre", "tent": "tienda de campaña", "tree": "árbol",
        "tree-autumn": "árbol de otoño", "rock-a": "roca", "signpost": "letrero de madera", "bottle": "botella",
        "tool-axe": "hacha", "tool-hoe": "azadón", "resource-wood": "leña", "workbench": "mesa de trabajo",
    },
}


def _bajar(paquete: str) -> Path:
    """El zip del paquete, desde la caché o de Kenney (la liga firmada de su botón Download)."""
    zip_ = CACHE / f"kenney_{paquete}.zip"
    if zip_.exists():
        return zip_
    s = requests.Session()
    s.headers.update(NAVEGADOR)
    pagina = s.get(f"https://kenney.nl/assets/{paquete}", timeout=30).text
    ident = re.search(r"data-download-id='([0-9a-f]+)'", pagina).group(1)
    url = s.get(f"https://kenney.nl/download-link/{ident}", timeout=30,
                headers={"Referer": f"https://kenney.nl/assets/{paquete}"}).json()["url"]
    CACHE.mkdir(parents=True, exist_ok=True)
    zip_.write_bytes(s.get(url, timeout=300).content)
    return zip_


def main() -> int:
    indice = {}
    for paquete, modelos in ELEGIDOS.items():
        corto = paquete.removesuffix("-kit")
        destino = MODELOS / corto
        (destino / "Textures").mkdir(parents=True, exist_ok=True)
        z = zipfile.ZipFile(_bajar(paquete))
        glb = {n.rsplit("/", 1)[-1][:-4]: n for n in z.namelist() if n.lower().endswith(".glb")}
        textura = next(n for n in z.namelist() if n.lower().endswith("textures/colormap.png") and "glb" in n.lower())
        (destino / "Textures" / "colormap.png").write_bytes(z.read(textura))
        for nombre, que in modelos.items():
            if nombre not in glb:
                print(f"no está en {paquete}: {nombre}")
                continue
            (destino / f"{nombre}.glb").write_bytes(z.read(glb[nombre]))
            indice[f"{corto}/{nombre}"] = que
    (MODELOS / "indice.json").write_text(json.dumps(indice, ensure_ascii=False, indent=1), encoding="utf-8")
    (MODELOS / "LICENCIA.txt").write_text(
        "Modelos de Kenney (https://kenney.nl), licencia Creative Commons CC0 1.0:\n"
        "https://creativecommons.org/publicdomain/zero/1.0/\n", encoding="utf-8")
    print(f"{len(indice)} modelos en {MODELOS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
