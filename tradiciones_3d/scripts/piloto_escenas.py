"""Piloto de escenas 3D para casos y cercanía (11/11/2026).

    C:\\illustrated-narrator\\.venv\\Scripts\\python.exe tradiciones_3d\\scripts\\piloto_escenas.py <slug> [--sin-render]

Rehace lo visual de un video ya generado sin tocar la voz: toma de
projects/<slug>/ la narración, los tiempos por palabra y los planos alineados, y
de ejemplos/escenas/<slug>.json qué se ve en cada plano (escenario, personajes,
cámara, etiquetas y, si hay, la evidencia real como sello). Sale
out/<slug>_escenas.mp4 y su hoja de contacto.

La evidencia no se reconstruye: {"evidencia": {"e": "e4"}} pone la captura real de
C:\\Android_in\\<slug>\\evidencia\\e4.jpg con el crédito de su manifest.json.
"""

import json
import shutil
import sys
import wave
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


def _dur(wav: Path) -> float:
    with wave.open(str(wav)) as w:
        return w.getnframes() / w.getframerate()


def credito(slug: str, clave: str) -> str:
    """El crédito corto de la evidencia: el que ya usa la ficha ("Infobae, 11/11/2026")."""
    datos = json.loads((ANDROID_IN / slug / "evidencia" / "manifest.json").read_text(encoding="utf-8"))[clave]
    partes = datos.get("huella", "").split("~")
    if len(partes) > 6 and partes[6]:
        return partes[6]
    return datos.get("autor") or datos.get("titular") or "archivo"


def armar(slug: str) -> Path:
    proyecto = NARRADOR / "projects" / slug
    destino = AQUI / "public" / "piloto" / slug
    destino.mkdir(parents=True, exist_ok=True)
    plan = json.loads((AQUI / "ejemplos" / "escenas" / f"{slug}.json").read_text(encoding="utf-8"))

    guion = load_guion(proyecto / "guion.json")
    palabras = captioned_transcript(guion, load_transcript(proyecto / "transcript.json")).words
    crudo = json.loads((proyecto / "guion.json").read_text(encoding="utf-8"))
    alineados = {p["id"]: p for p in json.loads((proyecto / "planos_alineados.json").read_text(encoding="utf-8"))}
    shutil.copy2(proyecto / "narracion.wav", destino / "narracion.wav")
    duracion = _dur(proyecto / "narracion.wav")

    escenas, marcas = [], []
    for p in crudo["planos"]:
        al = alineados.get(p["id"]) or {}
        if al.get("inicio_real_seg") is None or p["id"] not in plan["escenas"]:
            continue
        e = dict(plan["escenas"][p["id"]])
        e["id"] = p["id"]
        e["texto"] = p.get("narracion", "")
        ev = e.get("evidencia")
        if ev:
            # La captura real de la nota (multimedia/<e>_nota.png, página completa):
            # arriba vienen el medio, el titular y la foto, que es lo que se reconoce.
            origen = ANDROID_IN / slug / "multimedia" / f"{ev['e']}_nota.png"
            sello = destino / f"{ev['e']}_sello.jpg"
            with Image.open(origen) as im:
                im.convert("RGB").crop((0, 0, im.width, min(im.height, ev.get("alto", 1100)))).save(sello, quality=90)
            e["evidencia"] = {"img": f"piloto/{slug}/{sello.name}", "credito": credito(slug, ev["e"]),
                              **{k: ev[k] for k in ("desde", "hasta") if k in ev}}
        escenas.append(e)
        marcas.append({"id": p["id"], "ini": 0.0 if not marcas else float(al["inicio_real_seg"]),
                       "fin": float(al.get("fin_real_seg") or al["inicio_real_seg"])})

    props = {
        "escenas": escenas,
        "tiempos": {"duracion": round(duracion, 3), "escenas": marcas},
        "palabras": [{"t": round(w.start_seconds, 3), "f": round(w.end_seconds, 3), "w": w.text} for w in palabras],
        "audio": f"piloto/{slug}/narracion.wav",
        "ambiente": plan.get("ambiente", "noche"),
        "recreacion": True,
    }
    ruta = AQUI / "out" / f"{slug}_escenas.props.json"
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(props, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"props: {ruta} ({len(escenas)} escenas, {len(props['palabras'])} palabras, {duracion:.1f} s)")
    return ruta


def main(argv: list[str]) -> int:
    slug = argv[1]
    props = armar(slug)
    if "--sin-render" in argv:
        return 0
    video = AQUI / "out" / f"{slug}_escenas.mp4"
    render(props, video)
    hoja(video, AQUI / "out" / f"{slug}_escenas_hoja.jpg")
    print(f"video: {video}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
