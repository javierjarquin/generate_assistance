"""POC (14/10/2026): portada de TikTok para un capítulo ya generado.

TikTok usa por defecto el PRIMER cuadro del video, y en los videos de Remotion
ahí el contador estaba en 0 ("QUEDAN 0", "MURIERON 0" en el perfil de Javier).
Esto arma una imagen 1080x1920 con lo que ya está verificado en el guion:
  - fondo: la foto del lugar (Wikimedia) o la de la nota
  - nota: la parte de arriba de la nota de prensa del gancho (titular real)
  - dato: el contador del guion ("QUEDAN 3 PLAYAS PÚBLICAS")
Dos variantes para medir en el perfil: "nota" (titular protagonista) y "dato".

    C:\\illustrated-narrator\\.venv\\Scripts\\python.exe poc_remotion\\scripts\\portada.py <slug> [nota|dato|ambas]
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

POC = Path(__file__).resolve().parents[1]
ANDROID_IN = Path(r"C:\Android_in")
LOGO = POC.parent / "assets" / "dato_mata_gato_emblema.png"


def armar(slug: str, variante: str) -> Path:
    base = ANDROID_IN / slug
    guion = json.loads((base / "guion.json").read_text(encoding="utf-8"))
    man_ruta = base / "multimedia" / "manifest.json"
    notas = json.loads(man_ruta.read_text(encoding="utf-8"))["notas"] if man_ruta.exists() else {}
    destino = POC / "public" / slug / "portada"
    destino.mkdir(parents=True, exist_ok=True)

    def copiar(origen: Path) -> str:
        shutil.copy2(origen, destino / origen.name)
        return f"{slug}/portada/{origen.name}"

    piezas = {e["id"]: e for e in guion.get("evidencia", [])}
    # La nota: la de prensa del gancho (p00) si la hay; si no, la primera con captura.
    p00 = next((p for p in guion["planos"] if p["id"] == "p00"), {})
    candidatas = [e for e in (p00.get("visual") or {}).get("evidencia", []) if e in notas] + list(notas)
    pid = next((e for e in candidatas if notas[e].get("captura")), None)
    nota = {"src": copiar(base / "multimedia" / notas[pid]["captura"]), "credito": notas[pid]["credito"]} if pid else None

    # El fondo: la foto del lugar (real, Wikimedia) o, si no hay, una foto de la nota.
    fondo = None
    for e in guion.get("evidencia", []):
        if e.get("tipo") == "lugar" and (base / "evidencia" / f"{e['id']}.jpg").exists():
            fondo = copiar(base / "evidencia" / f"{e['id']}.jpg")
            break
    if fondo is None and pid and notas[pid].get("fotos"):
        fondo = copiar(base / "multimedia" / notas[pid]["fotos"][0])

    c = (guion.get("plus") or {}).get("contador") or {}
    if c.get("numero"):
        antes, numero, despues = c.get("antes", ""), f"{c['numero']:,}", c.get("despues", "")
    else:  # sin contador: el gancho del guion partido en dos
        palabras = str(guion.get("gancho", "")).split()
        antes, numero, despues = "", " ".join(palabras[:2]), " ".join(palabras[2:])
    logo = None
    if LOGO.exists():
        logo = copiar(LOGO)
    props = {"variante": variante, "fondo": fondo, "nota": nota, "antes": antes, "numero": numero,
             "despues": despues, "logo": logo, "palette": {"navy": "#0B1F3A", "gold": "#D4A537"}}
    ruta = destino / f"props_{variante}.json"
    ruta.write_text(json.dumps(props, ensure_ascii=False, indent=2), encoding="utf-8")
    return ruta


def render(slug: str, variante: str) -> Path:
    props = armar(slug, variante)
    salida = POC / "out" / f"{slug}_portada_{variante}.jpg"
    subprocess.run(["npx", "remotion", "still", "src/index.ts", "Portada", str(salida), f"--props={props}",
                    "--image-format=jpeg", "--jpeg-quality=92", "--gl=angle"],
                   cwd=POC, check=True, shell=(sys.platform == "win32"), capture_output=True)
    return salida


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    slug = sys.argv[1]
    cual = sys.argv[2] if len(sys.argv) > 2 else "ambas"
    for v in (["nota", "dato"] if cual == "ambas" else [cual]):
        print(render(slug, v))
