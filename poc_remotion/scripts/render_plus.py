"""POC CapituloPlus (13/10/2026): el mismo capítulo con valor visual para retención.

Parte de lo que arma render_capitulo.armar() (no lo cambia) y le agrega:
  - automático, sin Claude: qué tomas son fichas (para dibujarlas animadas con
    el dato resaltado), qué palabras van en rojo (las del texto_en_pantalla de
    su plano) y dónde van los destellos (inicio de cada plano "contexto");
  - de plus_datos/<slug>.json: contador del gancho, lugar del mapa y los dos
    lados de la contradicción. En producción, esos ~100 tokens los escribiría
    Claude en el guion; para el POC se sacaron a mano del guion ya verificado.
Las coordenadas salen de Photon (OpenStreetMap, gratis): Nominatim no responde
desde esta red (13/10/2026).

    C:\\illustrated-narrator\\.venv\\Scripts\\python.exe poc_remotion\\scripts\\render_plus.py <slug>
"""

import json
import re
import shutil
import subprocess
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from itertools import cycle, islice
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_capitulo import POC, armar  # noqa: E402

ANDROID_IN = Path(r"C:\Android_in")
CANCUN = (21.16, -86.85)
VACIAS = {"para", "como", "entre", "sobre", "desde", "hasta", "contra", "esta", "este", "cuando", "donde"}


def plano_txt(t: str) -> str:
    t = unicodedata.normalize("NFD", t.lower())
    return re.sub(r"[^a-z0-9ñ ]", "", "".join(c for c in t if unicodedata.category(c) != "Mn"))


def geocodificar(consulta: str, cerca=CANCUN, radio: float = 0.5) -> list[float]:
    q = urllib.parse.urlencode({"q": consulta, "limit": 1, "lat": cerca[0], "lon": cerca[1]})
    req = urllib.request.Request(f"https://photon.komoot.io/api/?{q}", headers={"User-Agent": "DatoMataGato-poc/1.0"})
    # Photon es público y gratis: a veces tarda o se satura (14/10/2026 se cortó
    # a los 30 s y el video salió sin mapa). Tres intentos antes de omitirlo.
    for intento in range(3):
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                feats = json.load(r)["features"]
            break
        except (OSError, ValueError):
            if intento == 2:
                raise
            time.sleep(5 * (intento + 1))
    if not feats:
        raise ValueError(f"Photon no encontró {consulta!r}")
    lon, lat = feats[0]["geometry"]["coordinates"]
    if abs(lat - cerca[0]) > radio or abs(lon - cerca[1]) > radio:
        raise ValueError(f"{consulta!r} cayó lejos ({lat}, {lon}): no se usa")
    return [lon, lat]


_UNIDADES = ("cero uno dos tres cuatro cinco seis siete ocho nueve diez once doce trece catorce quince "
             "dieciseis diecisiete dieciocho diecinueve veinte veintiuno veintidos veintitres veinticuatro "
             "veinticinco veintiseis veintisiete veintiocho veintinueve").split()
_DECENAS = {30: "treinta", 40: "cuarenta", 50: "cincuenta", 60: "sesenta", 70: "setenta", 80: "ochenta", 90: "noventa"}
_CENTENAS = {2: "doscientos", 3: "trescientos", 4: "cuatrocientos", 5: "quinientos", 6: "seiscientos",
             7: "setecientos", 8: "ochocientos", 9: "novecientos"}


def en_palabras(n: int) -> str:
    """104 -> 'ciento cuatro' (sin acentos, como plano_txt). Para comparar las
    cifras de una ficha con lo que dice la voz, que las lee en palabras."""
    if n < 30:
        return _UNIDADES[n]
    if n < 100:
        return _DECENAS[n // 10 * 10] + (f" y {_UNIDADES[n % 10]}" if n % 10 else "")
    if n < 1000:
        if n == 100:
            return "cien"
        c = "ciento" if n // 100 == 1 else _CENTENAS[n // 100]
        return c + (f" {en_palabras(n % 100)}" if n % 100 else "")
    if n < 1_000_000:
        miles = "mil" if n // 1000 == 1 else f"{en_palabras(n // 1000)} mil"
        return miles + (f" {en_palabras(n % 1000)}" if n % 1000 else "")
    millones = "un millon" if n // 1_000_000 == 1 else f"{en_palabras(n // 1_000_000)} millones"
    return millones + (f" {en_palabras(n % 1_000_000)}" if n % 1_000_000 else "")


def renglon_dicho(renglones: list[str], palabras: list[dict]) -> tuple[int, float]:
    """(renglón que la voz está diciendo, segundo en que lo empieza a decir) o (-1, 0).

    Corregido el 13/10/2026: antes se marcaba siempre el primer renglón con
    número, sin mirar la voz, y solo cuadraba en 3 de 13 fichas (Javier lo
    notó en el POC). Una cifra dicha completa ("ciento cuatro") vale 3; cada
    palabra del renglón (4 letras o más) que también se dice, 1. Sin coincidencia, no
    se resalta nada.
    """
    dichas = [plano_txt(w["text"]) for w in palabras]
    texto = f" {' '.join(dichas)} "
    mejor, cuando, puntos_mejor = -1, 0.0, 0
    for k, r in enumerate(renglones):
        puntos, primera = 0, None
        for cifra in re.findall(r"\d+", r):  # "32.9" -> 32 y 9: la voz dice "treinta y dos punto nueve"
            frase = en_palabras(int(cifra))
            if f" {frase} " in texto:
                puntos += 3
                ini = frase.split()[0]
                primera = min(primera, dichas.index(ini)) if primera is not None else dichas.index(ini)
        for t in plano_txt(r).split():
            if len(t) >= 4 and not t.isdigit() and t not in VACIAS and t in dichas:
                puntos += 1
                primera = min(primera, dichas.index(t)) if primera is not None else dichas.index(t)
        if puntos > puntos_mejor:
            mejor, puntos_mejor, cuando = k, puntos, palabras[primera]["start"]
    return mejor, cuando


def fichas_por_toma(slug: str, props: dict) -> dict:
    """La toma n de un plano es la pieza cycle(evidencia del plano)[n-1]: así las
    reparte evidencia._asignar (con el préstamo del plano anterior si no tiene)."""
    base = ANDROID_IN / slug
    guion = json.loads((base / "guion.json").read_text(encoding="utf-8"))
    hechas = json.loads((base / "evidencia" / "manifest.json").read_text(encoding="utf-8"))
    piezas = {e["id"]: e for e in guion.get("evidencia", [])}
    listas = [e["id"] for e in guion.get("evidencia", []) if e["id"] in hechas]
    ultimas, propias_de = listas[:3], {}
    for p in guion["planos"]:
        if p.get("seccion") == "identidad_cierre":
            continue
        propias = [e for e in (p.get("visual") or {}).get("evidencia", []) if e in hechas] or ultimas or listas
        ultimas = propias
        propias_de[p["id"]] = list(islice(cycle(propias), 5))
    out = {}
    planos = props["planos"]
    for j, pl in enumerate(planos):
        orden = propias_de.get(pl["id"])
        if not orden or not pl["shots"]:
            continue
        # Igual que CapituloPlus: el plano reparte su tiempo en partes iguales entre sus tomas.
        fin = planos[j + 1]["start"] if j + 1 < len(planos) else props["durationSec"]
        por = (fin - pl["start"]) / len(pl["shots"])
        for i, src in enumerate(pl["shots"]):
            n = int(re.search(r"_(\d+)\.png$", src).group(1))
            pieza = piezas.get(orden[n - 1])
            if pieza and pieza.get("tipo") == "ficha":
                renglones = pieza.get("renglones", [])
                a = pl["start"] + i * por
                voz = [w for w in props["words"] if a - 0.2 <= w["start"] < a + por]
                resaltar, cuando = renglon_dicho(renglones, voz)
                out.setdefault(pl["id"], {})[str(i)] = {
                    "titulo": pieza.get("titulo", ""), "renglones": renglones,
                    "fuente": pieza.get("fuente", ""), "resaltar": resaltar,
                    # El resaltador arranca cuando la voz lo dice (no antes de 0.4 s).
                    "resaltarDesde": round(max(0.4, cuando - a), 2) if resaltar >= 0 else 0}
    return out


def piezas_por_toma(slug: str, planos: list[dict]) -> dict[str, list[str]]:
    """plano -> pieza de evidencia de cada toma (cycle de la evidencia del plano,
    como la reparte evidencia._asignar)."""
    base = ANDROID_IN / slug
    guion = json.loads((base / "guion.json").read_text(encoding="utf-8"))
    hechas = json.loads((base / "evidencia" / "manifest.json").read_text(encoding="utf-8"))
    listas = [e["id"] for e in guion.get("evidencia", []) if e["id"] in hechas]
    ultimas, out = listas[:3], {}
    for p in guion["planos"]:
        if p.get("seccion") == "identidad_cierre":
            continue
        propias = [e for e in (p.get("visual") or {}).get("evidencia", []) if e in hechas] or ultimas or listas
        ultimas = propias
        orden = list(islice(cycle(propias), 5))
        pl = next((x for x in planos if x["id"] == p["id"]), None)
        if pl:
            out[p["id"]] = [orden[int(re.search(r"_(\d+)\.png$", s).group(1)) - 1] for s in pl["shots"]]
    return out


def medios_por_toma(slug: str, props: dict) -> dict:
    """Evidencia en movimiento (14/10/2026): reparte lo que juntó multimedia.py.

    Nota de prensa: la 1a vez que sale, la nota animada (baja al dato y lo
    resalta); la 2a, su foto; la 3a, la otra foto; después, archivo. Una pieza
    repetida dentro del mismo plano se cambia por una toma de archivo. Así el
    mismo titular no sale cuatro veces igual (Javier: "muy planos, solo texto").
    """
    man_ruta = ANDROID_IN / slug / "multimedia" / "manifest.json"
    if not man_ruta.exists():
        return {}
    man = json.loads(man_ruta.read_text(encoding="utf-8"))
    origen = man_ruta.parent
    destino = POC / "public" / slug / "media"
    destino.mkdir(parents=True, exist_ok=True)

    def copiar(nombre: str) -> str:
        shutil.copy2(origen / nombre, destino / nombre)
        return f"{slug}/media/{nombre}"

    archivo = list(man.get("archivo", []))
    vistas: dict[str, int] = {}
    out: dict = {}
    for plano, piezas in piezas_por_toma(slug, props["planos"]).items():
        en_plano: set = set()
        for i, pid in enumerate(piezas):
            nota = man["notas"].get(pid)
            medio = None
            if nota:
                k = vistas.get(pid, 0)
                vistas[pid] = k + 1
                if k == 0 and nota.get("captura"):
                    medio = {"tipo": "nota", "src": copiar(nota["captura"]), "credito": nota["credito"],
                             "alto": nota.get("alto"), "caja": nota.get("caja")}
                elif 1 <= k <= len(nota.get("fotos", [])):
                    medio = {"tipo": "foto", "src": copiar(nota["fotos"][k - 1]), "credito": nota["credito"]}
                elif nota.get("videos"):
                    medio = {"tipo": "video", "src": copiar(nota["videos"][0]), "credito": f"Video: {nota['credito']}"}
            if medio is None and pid in en_plano and archivo:
                a = archivo.pop(0)
                medio = {"tipo": "video", "src": copiar(a["src"]), "credito": a["credito"]}
            en_plano.add(pid)
            if medio:
                out.setdefault(plano, {})[str(i)] = medio
    return out


def marcar_enfasis(props: dict) -> int:
    claves = {}
    for p in props["planos"]:
        claves[p["id"]] = {w for w in plano_txt(p.get("texto", "")).split()
                           if (len(w) >= 4 or w.isdigit()) and w not in VACIAS}
    n = 0
    for w in props["words"]:
        pl = next((p for p in reversed(props["planos"]) if p["start"] <= w["start"] + 0.01), None)
        if pl and plano_txt(w["text"]) in claves.get(pl["id"], set()):
            w["enfasis"] = True
            n += 1
    return n


# Cerca de dónde buscar el lugar del mapa, por tema del slug (guion-<tema>-...).
# (centro, radio en grados). Cancún abarca la Riviera Maya: Playa del Carmen
# queda a ~0.53° y Tulum a ~0.96° (con 0.5 se perdió el mapa de la Quinta
# Avenida, 14/10/2026). Más allá ya es otro estado: se omite.
CENTROS = {"cancun": (CANCUN, 1.1), "cdmx": ((19.43, -99.13), 0.5)}


def datos_plus(slug: str) -> dict:
    """plus_datos/<slug>.json (los del POC, escritos a mano) o, si no hay, el
    bloque "plus" que Claude escribe en el guion (desde el 13/10/2026)."""
    ruta = POC / "plus_datos" / f"{slug}.json"
    if ruta.exists():
        return json.loads(ruta.read_text(encoding="utf-8"))
    try:
        guion = json.loads((ANDROID_IN / slug / "guion.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return guion.get("plus") or {}


def _parte(nombre: str, fn):
    """Una animación que falla se omite, pero el video sale igual."""
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001
        print(f"plus: sin {nombre} ({type(exc).__name__}: {exc})")
        return None


def armar_plus(slug: str) -> Path:
    ruta = armar(slug)
    props = json.loads(ruta.read_text(encoding="utf-8"))
    datos = datos_plus(slug)
    inicio = {p["id"]: p["start"] for p in props["planos"]}
    tema = slug.split("-")[1] if slug.count("-") >= 2 else ""

    props["fichas"] = _parte("fichas animadas", lambda: fichas_por_toma(slug, props)) or {}
    props["medios"] = _parte("evidencia en movimiento", lambda: medios_por_toma(slug, props)) or {}
    enf = _parte("palabras en rojo", lambda: marcar_enfasis(props)) or 0
    props["destellos"] = [p["start"] for p in props["planos"][1:] if p["seccion"] == "contexto"]

    def contador():
        c = datos["contador"]
        if not isinstance(c.get("numero"), int) or c["numero"] <= 0:
            raise ValueError(f"número inválido {c.get('numero')!r}")
        return {"plano": c.get("plano", "p00"), "numero": c["numero"],
                "antes": str(c.get("antes", "")), "despues": str(c.get("despues", ""))}
    props["contador"] = _parte("contador", contador) if datos.get("contador") else None

    def mapa():
        m = datos["mapa"]
        if m.get("plano") not in inicio:
            raise ValueError(f"plano {m.get('plano')!r} no existe")
        centro = m.get("centro")
        if not centro:
            if tema in CENTROS:
                centro = geocodificar(m["consulta"], *CENTROS[tema])
            else:
                raise ValueError(f"sin ciudad de referencia para el tema {tema!r}")
        return {"plano": m["plano"], "centro": centro, "etiqueta": m.get("etiqueta") or m["consulta"].upper(),
                "desde": float(m.get("desde", 0.0)), "dur": float(m.get("dur", 3.6))}
    props["mapa"] = _parte("mapa", mapa) if datos.get("mapa") else None

    def contradiccion():
        c = datos["contradiccion"]
        t0 = inicio[c["plano"]]
        cuando = next((w["start"] for w in props["words"]
                       if w["start"] >= t0 and plano_txt(w["text"]) == plano_txt(c.get("abajo_en", ""))), t0 + 2.5)
        for lado in ("arriba", "abajo"):
            if not c[lado].get("renglones"):
                raise ValueError(f"{lado} sin renglones")
        return {"plano": c["plano"], "arriba": c["arriba"], "abajo": c["abajo"],
                "abajoDesde": round(cuando - t0, 2), "resaltar": c.get("resaltar", ""), "fuente": c.get("fuente", "")}
    props["contradiccion"] = _parte("contradicción", contradiccion) if datos.get("contradiccion") else None

    ruta.write_text(json.dumps(props, ensure_ascii=False, indent=2), encoding="utf-8")
    fichas = sum(len(v) for v in props["fichas"].values())
    tipos = [m["tipo"] for v in props["medios"].values() for m in v.values()]
    print(f"plus: {fichas} fichas animadas, {enf} palabras en rojo, "
          f"{tipos.count('nota')} notas animadas, {tipos.count('foto')} fotos, {tipos.count('video')} videos, {len(props['destellos'])} destellos, "
          f"contador={'sí' if props['contador'] else 'no'}, mapa={'sí' if props['mapa'] else 'no'}, "
          f"contradicción={'sí' if props['contradiccion'] else 'no'}")
    return ruta


def render(slug: str, props: Path) -> Path:
    salida = POC / "out" / f"{slug}_plus.mp4"
    inicio = time.time()
    subprocess.run(["npx", "remotion", "render", "src/index.ts", "CapituloPlus", str(salida),
                    f"--props={props}", "--codec=h264", "--crf=20", "--timeout=120000", "--gl=angle"],
                   cwd=POC, check=True, shell=(sys.platform == "win32"))
    print(f"render: {salida} en {time.time() - inicio:.0f} s")
    return salida


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    slug = next(a for a in sys.argv[1:] if not a.startswith("--"))
    ruta = armar_plus(slug)
    if "--solo-props" not in sys.argv:
        render(slug, ruta)
