"""POC Remotion: un capítulo YA generado por illustrated-narrator -> MP4 con Remotion.

No toca el pipeline: lee lo que `narrator generate` dejó en projects/<slug>/
(narracion.wav, transcript.json con tiempos por palabra, planos_alineados.json,
guion.json, images/), arma public/<slug>/props.json y renderiza a out/<slug>.mp4.

Se corre con el Python del narrador (para reusar, sin modificarlas, sus
funciones de carga y la que pone el TEXTO del guion sobre los TIEMPOS de
Whisper, así en pantalla no salen nombres mal oídos):

    C:\\illustrated-narrator\\.venv\\Scripts\\python.exe poc_remotion\\scripts\\render_capitulo.py guion-cancun-imss-citas
    (--solo-props para armar el JSON sin renderizar)
"""

import json
import shutil
import subprocess
import sys
import time
import wave
from pathlib import Path

POC = Path(__file__).resolve().parents[1]
NARRADOR = POC.parent
sys.path.insert(0, str(NARRADOR / "src"))

from illustrated_narrator.domain.services.forced_aligner import captioned_transcript  # noqa: E402
from illustrated_narrator.domain.services.script_loader import load_guion  # noqa: E402
from illustrated_narrator.domain.services.transcript_store import load_transcript  # noqa: E402

PALETA = {"navy": "#0B1F3A", "gold": "#D4A537"}
LOGO = NARRADOR / "assets" / "dato_mata_gato_emblema.png"


def duracion_wav(ruta: Path) -> float:
    with wave.open(str(ruta)) as w:
        return w.getnframes() / w.getframerate()


def armar(slug: str) -> Path:
    proyecto = NARRADOR / "projects" / slug
    destino = POC / "public" / slug
    (destino / "img").mkdir(parents=True, exist_ok=True)

    guion = load_guion(proyecto / "guion.json")
    crudo = json.loads((proyecto / "guion.json").read_text(encoding="utf-8"))
    transcript = load_transcript(proyecto / "transcript.json")
    palabras = captioned_transcript(guion, transcript).words
    alineados = {p["id"]: p for p in json.loads((proyecto / "planos_alineados.json").read_text(encoding="utf-8"))}

    shutil.copy2(proyecto / "narracion.wav", destino / "narracion.wav")
    logo = None
    if LOGO.exists():
        shutil.copy2(LOGO, destino / "logo.png")
        logo = f"{slug}/logo.png"

    planos = []
    for p in crudo["planos"]:
        al = alineados.get(p["id"]) or {}
        if al.get("inicio_real_seg") is None:
            continue  # sin alinear: el pipeline tampoco lo renderiza
        tipo = (p.get("visual") or {}).get("tipo", "")
        shots = []
        if tipo != "grafico_movimiento":
            # Las tomas que usa el pipeline: images/<plano>_<n>.png, en su versión
            # limpia (bordes recortados) si existe.
            for img in sorted((proyecto / "images").glob(f"{p['id']}_*.png")):
                limpia = proyecto / "images" / "clean" / img.name
                fuente = limpia if limpia.exists() else img
                shutil.copy2(fuente, destino / "img" / img.name)
                shots.append(f"{slug}/img/{img.name}")
        planos.append({
            "id": p["id"], "seccion": p.get("seccion", ""), "tipo": tipo,
            "start": float(al["inicio_real_seg"]), "end": float(al.get("fin_real_seg") or al["inicio_real_seg"]),
            "texto": p.get("texto_en_pantalla", ""), "shots": shots,
        })

    # Música: solo si el capítulo tiene un archivo real en assets/ (el guion solo
    # trae descripciones). Javier la pone desde TikTok, así que hoy queda en null.
    musica = None
    for nombre in ("music.mp3", "music.wav"):
        if (proyecto / "assets" / nombre).exists() and "--con-musica" in sys.argv:
            shutil.copy2(proyecto / "assets" / nombre, destino / nombre)
            musica = f"{slug}/{nombre}"

    props = {
        "slug": slug,
        "durationSec": round(duracion_wav(proyecto / "narracion.wav"), 3),
        "audio": f"{slug}/narracion.wav",
        "musica": musica, "musicaVolumen": 0.12,
        "logo": logo, "palette": PALETA,
        "words": [{"text": w.text, "start": round(w.start_seconds, 3), "end": round(w.end_seconds, 3)}
                  for w in palabras],
        "planos": planos,
    }
    ruta = destino / "props.json"
    ruta.write_text(json.dumps(props, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"props: {ruta} ({len(planos)} planos, {len(props['words'])} palabras, {props['durationSec']} s)")
    return ruta


def render(slug: str, props: Path) -> Path:
    salida = POC / "out" / f"{slug}.mp4"
    salida.parent.mkdir(exist_ok=True)
    inicio = time.time()
    subprocess.run(["npx", "remotion", "render", "src/index.ts", "Capitulo", str(salida),
                    f"--props={props}", "--codec=h264", "--crf=20"],
                   cwd=POC, check=True, shell=(sys.platform == "win32"))
    print(f"render: {salida} en {time.time() - inicio:.0f} s")
    return salida


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    slug = next(a for a in sys.argv[1:] if not a.startswith("--"))
    ruta = armar(slug)
    if "--solo-props" not in sys.argv:
        render(slug, ruta)
