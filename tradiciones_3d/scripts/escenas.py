"""Escenas 3D en vez del formato "noticia" (11/11/2026):

    C:\\illustrated-narrator\\.venv\\Scripts\\python.exe tradiciones_3d\\scripts\\escenas.py <slug> [--hoja]

Es el piloto (scripts/piloto_escenas.py) hecho producción. No toca la voz ni los
subtítulos: toma de projects/<slug>/ lo que dejó `narrator generate` (la
narración, los tiempos por palabra y planos_alineados.json) y de
C:\\Android_in\\<slug>\\escenas.json lo que se ve en cada plano, que escribió
Claude con el catálogo de public/modelos/indice_escenas.json.

Lo que suma sobre el piloto: el emblema del canal en la esquina, el cierre de
marca de los videos de hoy, transiciones cortas entre escenas y las dos
sorpresas del render plus (el gato que se asoma y el cuadro crudo).

La evidencia NO se reconstruye: {"evidencia": {"e": "e4"}} pone la captura real
(multimedia/e4_nota.png, o evidencia/e4.jpg) como sello con su fuente.

La última línea es "RENDER <ruta>": el bot la busca. Lo copiado a public/<slug>
lo borra el bot al terminar.
"""

import json
import re
import shutil
import sys
import time
import wave
import zlib
from pathlib import Path

from PIL import Image

AQUI = Path(__file__).resolve().parents[1]
NARRADOR = AQUI.parent
ANDROID_IN = Path(r"C:\Android_in")
sys.path.insert(0, str(NARRADOR / "src"))
sys.path.insert(0, str(AQUI / "scripts"))

from illustrated_narrator.domain.services.forced_aligner import captioned_transcript  # noqa: E402
from illustrated_narrator.domain.services.script_loader import load_guion  # noqa: E402
from illustrated_narrator.domain.services.transcript_store import load_transcript  # noqa: E402
from render import hoja, render  # noqa: E402

LOGO = NARRADOR / "assets" / "dato_mata_gato_emblema.png"
GATO = NARRADOR / "assets" / "gato_asomado.png"
GATO_DUR = 0.6
CRUDO_DUR = 0.5
TRANSICION = 0.18  # s de parpadeo en cada corte
# El alto del sello de la nota recortada: arriba vienen el medio, el titular y
# la foto, que es lo que se reconoce de un vistazo.
ALTO_SELLO = 1100
FIRMA = "Dato Mata Gato"


def _dur(wav: Path) -> float:
    with wave.open(str(wav)) as w:
        return w.getnframes() / w.getframerate()


def credito(slug: str, clave: str) -> str:
    """El crédito corto de la evidencia: el que ya usa la ficha ("Infobae, 11/11/2026")."""
    try:
        datos = json.loads((ANDROID_IN / slug / "evidencia" / "manifest.json")
                           .read_text(encoding="utf-8-sig"))[clave]
    except (OSError, ValueError, KeyError):
        return "archivo"
    partes = str(datos.get("huella", "")).split("~")
    if len(partes) > 6 and partes[6]:
        return partes[6]
    return datos.get("autor") or datos.get("titular") or "archivo"


def sello(slug: str, destino: Path, ev: dict) -> dict | None:
    """La captura real de la pieza `ev["e"]`, lista para el render."""
    clave = str(ev.get("e") or "")
    base = ANDROID_IN / slug
    # La captura de la nota solo si el manifest la da por buena: una página que
    # resultó ser un captcha queda sin "captura" (11/11/2026) y entonces el
    # sello es la pieza de evidencia, que sí se verificó.
    try:
        man = json.loads((base / "multimedia" / "manifest.json").read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        man = {}
    captura = ((man.get("notas") or {}).get(clave) or {}).get("captura")
    nota = base / "multimedia" / (captura or f"{clave}_nota.png")
    pieza = base / "evidencia" / f"{clave}.jpg"
    origen = nota if (captura and nota.exists()) else pieza
    if not clave or not origen.exists():
        print(f"sin evidencia para el sello {clave!r}", flush=True)
        return None
    salida = destino / f"{clave}_sello.jpg"
    try:
        with Image.open(origen) as im:
            # De la nota, solo la parte de arriba; una foto va entera.
            alto = min(im.height, int(ev.get("alto", ALTO_SELLO))) if origen == nota else im.height
            im.convert("RGB").crop((0, 0, im.width, alto)).save(salida, quality=90)
    except OSError as exc:
        print(f"no se pudo recortar {origen.name}: {exc}", flush=True)
        return None
    return {"img": f"{slug}/{salida.name}", "credito": credito(slug, clave),
            **{k: float(ev[k]) for k in ("desde", "hasta") if k in ev}}


def foto_cruda(slug: str) -> Path | None:
    """La foto real del tema para el cuadro crudo, en el mismo orden que el
    render plus: el cuadro de la publicación de redes, la foto de una nota, y
    por último la del lugar o la persona."""
    base = ANDROID_IN / slug
    try:
        hechas = json.loads((base / "evidencia" / "manifest.json").read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        hechas = {}
    for pid, meta in hechas.items():
        if meta.get("tipo") == "video_red" and (base / "evidencia" / f"{pid}.jpg").exists():
            return base / "evidencia" / f"{pid}.jpg"
    try:
        man = json.loads((base / "multimedia" / "manifest.json").read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        man = {}
    for nota in (man.get("notas") or {}).values():
        for f in nota.get("fotos") or []:
            if (base / "multimedia" / f).exists():
                return base / "multimedia" / f
    for tipo in ("lugar", "persona"):
        for pid, meta in hechas.items():
            if meta.get("tipo") == tipo and (base / "evidencia" / f"{pid}.jpg").exists():
                return base / "evidencia" / f"{pid}.jpg"
    return None


def _ocupado(escenas: list[dict], marcas: list[dict], fin_cierre: float | None) -> list[tuple[float, float]]:
    """Tramos (segundos) donde no va una sorpresa: el gancho, el cierre y donde
    está puesto un sello de evidencia."""
    por_id = {e["id"]: e for e in escenas}
    fuera = [(marcas[0]["ini"], marcas[0]["fin"])] if marcas else []
    if fin_cierre is not None:
        fuera.append((fin_cierre, 1e9))
    for j, m in enumerate(marcas):
        ev = (por_id.get(m["id"]) or {}).get("evidencia")
        if not ev:
            continue
        fin = marcas[j + 1]["ini"] if j + 1 < len(marcas) else m["fin"]
        largo = max(0.1, fin - m["ini"])
        fuera.append((m["ini"] + float(ev.get("desde", 0.35)) * largo,
                      m["ini"] + float(ev.get("hasta", 0.95)) * largo))
    return fuera


def _momento(total: float, fuera: list[tuple[float, float]], cortes: list[float], rng: float,
             desde: float, hasta: float, dur: float, lejos_de: float | None = None) -> float | None:
    """Un segundo entre `desde` y `hasta` (fracción del video) que no pise lo
    ocupado ni un corte de escena; `rng` (0-1) decide cuál de los posibles."""
    libres, t = [], desde * total
    while t + dur <= hasta * total:
        pisa = any(a - 0.3 < t + dur and t < b + 0.3 for a, b in fuera)
        corte = any(t - 0.4 < c < t + dur + 0.4 for c in cortes)
        cerca = lejos_de is not None and abs(t - lejos_de) < 6
        if not (pisa or corte or cerca):
            libres.append(round(t, 2))
        t += 0.1
    return libres[int(rng * len(libres))] if libres else None


def sorpresas(slug: str, destino: Path, escenas: list[dict], marcas: list[dict], duracion: float,
              fin_cierre: float | None) -> tuple[dict | None, dict | None]:
    """El gato que se asoma y el cuadro crudo (06/11/2026). Fijo por slug: el
    mismo video siempre sale igual."""
    semilla = zlib.crc32(f"sorpresa:{slug}".encode("utf-8"))
    dado = [((semilla >> k) & 0xFF) / 256 for k in (0, 8, 16, 24)]
    fuera = _ocupado(escenas, marcas, fin_cierre)
    cortes = [m["ini"] for m in marcas]

    crudo = None
    foto = foto_cruda(slug)
    # A la mitad, donde la fórmula pone la segunda pregunta.
    t = _momento(duracion, fuera, cortes, dado[0], 0.45, 0.62, CRUDO_DUR) if foto else None
    if t is not None:
        shutil.copy2(foto, destino / f"crudo{foto.suffix}")
        crudo = {"t": t, "dur": CRUDO_DUR, "src": f"{slug}/crudo{foto.suffix}"}

    gato = None
    t = _momento(duracion, fuera, cortes, dado[1], 0.22, 0.85, GATO_DUR,
                 lejos_de=crudo["t"] if crudo else None)
    if t is not None and GATO.exists():
        shutil.copy2(GATO, destino / "gato.png")
        # Entre los subtítulos (300) y el letrero (1330).
        gato = {"t": t, "dur": GATO_DUR, "src": f"{slug}/gato.png", "lado": "izq" if dado[2] < 0.5 else "der",
                "y": round(600 + dado[3] * 560), "giro": round(12 + dado[2] * 20)}
    return gato, crudo


def _texto_de_cierre(plano: dict, guion: dict) -> str:
    """Lo que dice la tarjeta de cierre, arriba de la firma del canal: el
    texto_en_pantalla del plano de identidad_cierre, como el render de hoy. Si
    ese texto ES el nombre del canal, se queda vacío: abajo ya dice
    DATO MATA GATO y salía dos veces."""
    texto = str(plano.get("texto_en_pantalla") or "").strip()
    normal = re.sub(r"[^a-z]", "", texto.lower())
    return "" if normal == re.sub(r"[^a-z]", "", FIRMA.lower()) else texto


def armar(slug: str, plan: dict) -> Path:
    proyecto = NARRADOR / "projects" / slug
    destino = AQUI / "public" / slug
    destino.mkdir(parents=True, exist_ok=True)

    guion = load_guion(proyecto / "guion.json")
    palabras = captioned_transcript(guion, load_transcript(proyecto / "transcript.json")).words
    crudo_guion = json.loads((proyecto / "guion.json").read_text(encoding="utf-8"))
    alineados = {p["id"]: p for p in json.loads((proyecto / "planos_alineados.json").read_text(encoding="utf-8"))}
    shutil.copy2(proyecto / "narracion.wav", destino / "narracion.wav")
    duracion = _dur(proyecto / "narracion.wav")

    escenas, marcas, cierre, sin_escena = [], [], None, []
    for p in crudo_guion["planos"]:
        al = alineados.get(p["id"]) or {}
        if al.get("inicio_real_seg") is None:
            continue  # sin alinear: el pipeline tampoco lo renderiza
        ini = 0.0 if not marcas else float(al["inicio_real_seg"])
        fin = float(al.get("fin_real_seg") or al["inicio_real_seg"])
        # El cierre de marca tapa la escena, así que ese plano no necesita una.
        es_cierre = p.get("seccion") == "identidad_cierre"
        if es_cierre:
            cierre = {"desde": round(ini, 3), "texto": _texto_de_cierre(p, crudo_guion)}
        escena = (plan.get("escenas") or {}).get(p["id"])
        if escena is None:
            if not es_cierre:
                sin_escena.append(p["id"])
                continue
            escena = {"visual": [{"objeto": "Suelo"}]}
        e = dict(escena)
        e["id"] = p["id"]
        e["texto"] = p.get("narracion", "")
        if ev := e.get("evidencia"):
            e["evidencia"] = sello(slug, destino, ev) or None
            if e["evidencia"] is None:
                e.pop("evidencia")
        escenas.append(e)
        marcas.append({"id": p["id"], "ini": round(ini, 3), "fin": round(fin, 3)})
    if sin_escena:
        print(f"planos sin escena (se queda la anterior): {', '.join(sin_escena)}", flush=True)

    logo = None
    if LOGO.exists():
        shutil.copy2(LOGO, destino / "logo.png")
        logo = f"{slug}/logo.png"
    if cierre is not None:
        cierre["logo"] = logo
    gato, cuadro = (None, None) if (crudo_guion.get("plus") or {}).get("sin_sorpresas") else sorpresas(
        slug, destino, escenas, marcas, duracion, cierre["desde"] if cierre else None)

    props = {
        "escenas": escenas,
        "tiempos": {"duracion": round(duracion, 3), "escenas": marcas},
        "palabras": [{"t": round(w.start_seconds, 3), "f": round(w.end_seconds, 3), "w": w.text} for w in palabras],
        "audio": f"{slug}/narracion.wav",
        "ambiente": plan.get("ambiente", "noche"),
        "recreacion": True,
        "logo": logo, "cierre": cierre, "gato": gato, "crudo": cuadro,
        "transicion": TRANSICION,
    }
    ruta = destino / "props.json"
    ruta.write_text(json.dumps(props, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"escenas: {len(escenas)} escenas, {len(props['palabras'])} palabras, {duracion:.1f} s, "
          f"cierre={'sí' if cierre else 'no'}, gato={_mmss(gato['t']) if gato else 'no'}, "
          f"cuadro crudo={_mmss(cuadro['t']) if cuadro else 'no'}", flush=True)
    return ruta


def _mmss(t: float) -> str:
    return f"{int(t) // 60}:{int(t) % 60:02d}"


def plan_de(slug: str) -> dict:
    """Las escenas que escribió Claude. Las del piloto (ejemplos/escenas) sirven
    igual, para poder rehacer un video viejo sin volver a pedirlas."""
    for ruta in (ANDROID_IN / slug / "escenas.json", AQUI / "ejemplos" / "escenas" / f"{slug}.json"):
        if ruta.exists():
            return json.loads(ruta.read_text(encoding="utf-8"))
    raise SystemExit(f"no hay escenas para {slug}: falta {ANDROID_IN / slug / 'escenas.json'}")


def main(argv: list[str]) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    slug = next(a for a in argv if not a.startswith("--"))
    props = armar(slug, plan_de(slug))
    if "--solo-props" in argv:
        print(f"PROPS {props}", flush=True)
        return 0
    salida = AQUI / "out" / f"{slug}.mp4"
    salida.unlink(missing_ok=True)
    antes = time.time()
    render(props, salida)
    print(f"render: {time.time() - antes:.0f} s", flush=True)
    if "--hoja" in argv:
        hoja(salida, AQUI / "out" / f"{slug}_hoja.jpg")
    print(f"RENDER {salida}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
