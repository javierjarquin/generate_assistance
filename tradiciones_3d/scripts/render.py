"""Video del nicho "el porqué de las tradiciones" (30/10/2026), de punta a punta:

    C:\\illustrated-narrator\\.venv\\Scripts\\python.exe tradiciones_3d\\scripts\\render.py <slug> [--hoja]

1. Voz Fish 3 por escena (la misma voz y ajustes que producción) en
   C:\\Android_in\\<slug>\\voz_3d\\; una escena cuyo texto no cambió no se vuelve a pedir.
2. Las escenas se pegan con 0.35 s de silencio -> public/<slug>/voz.wav.
3. Whisper da los tiempos por palabra; las palabras salen del guion (Whisper
   escribe mal el náhuatl), alineadas con difflib.
4. remotion render -> out/<slug>.mp4 (75 s tardan ~1 min). Con --hoja, también
   out/<slug>_hoja.jpg (un cuadro por segundo) para revisarlo de un vistazo.

La última línea es "RENDER <ruta>": el bot la busca. Lo copiado a public/<slug>
lo borra el bot al terminar.
"""

import difflib
import hashlib
import json
import re
import subprocess
import sys
import time
import wave
from pathlib import Path

AQUI = Path(__file__).resolve().parents[1]
ANDROID_IN = Path(r"C:\Android_in")
TTS_KOKORO_SRC = r"C:\tts-kokoro\src"
VOICESTUDIO = "http://localhost:3900/v1/audio/speech"
VOZ = {"model": "omnivoice", "voice": "cbbc2aa7", "response_format": "wav", "language": "es",
       "num_step": 32, "seed": 1234}
PAUSA = 0.35  # s de silencio entre escenas
FFMPEG = "ffmpeg"


def _wav_dur(ruta: Path) -> float:
    with wave.open(str(ruta)) as w:
        return w.getnframes() / w.getframerate()


def voz(guion: dict, trabajo: Path, salida: Path) -> dict:
    """Una voz por escena y el audio pegado. Devuelve {"duracion", "escenas": [{id, ini, fin}]}."""
    import requests

    sys.path.insert(0, TTS_KOKORO_SRC)
    from tts_kokoro.domain.text_normalizer import normalize_text

    trabajo.mkdir(parents=True, exist_ok=True)
    silencio = trabajo / "silencio.wav"
    subprocess.run([FFMPEG, "-v", "error", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", str(PAUSA),
                    str(silencio)], check=True)
    lista, escenas, t = [], [], 0.0
    for e in guion["escenas"]:
        texto = normalize_text(e["texto"])
        huella = hashlib.sha1(json.dumps([texto, VOZ], ensure_ascii=False).encode("utf-8")).hexdigest()[:10]
        wav = trabajo / f"{e['id']}-{huella}.wav"
        if not wav.exists():
            inicio = time.time()
            r = requests.post(VOICESTUDIO, timeout=1800, json={**VOZ, "input": texto})
            r.raise_for_status()
            wav.write_bytes(r.content)
            print(f"voz {e['id']}: {time.time() - inicio:.0f} s", flush=True)
        dur = _wav_dur(wav)
        escenas.append({"id": e["id"], "ini": round(t, 3), "fin": round(t + dur, 3)})
        t += dur + PAUSA
        lista += [wav, silencio]
    (trabajo / "lista.txt").write_text("".join(f"file '{p.as_posix()}'\n" for p in lista), encoding="utf-8")
    salida.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([FFMPEG, "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(trabajo / "lista.txt"),
                    "-ar", "48000", str(salida)], check=True)
    return {"duracion": round(t, 3), "escenas": escenas}


def _norma(w: str) -> str:
    return re.sub(r"[^\wáéíóúüñ]", "", w.lower())


def alinear(oidas: list[dict], escritas: list[str]) -> list[dict]:
    """Las palabras del guion con los tiempos de lo que oyó Whisper. Lo que no
    coincide se reparte parejo en el tramo oído."""
    sm = difflib.SequenceMatcher(None, [_norma(w["w"]) for w in oidas], [_norma(w) for w in escritas], autojunk=False)
    palabras = []
    for op, a1, a2, b1, b2 in sm.get_opcodes():
        if op == "equal":
            palabras += [{**oidas[a1 + k], "w": escritas[b1 + k]} for k in range(b2 - b1)]
        elif b2 > b1:
            if oidas:
                t0 = oidas[a1]["t"] if a1 < len(oidas) else oidas[-1]["f"]
            else:
                t0 = palabras[-1]["f"] if palabras else 0.0
            t1 = oidas[a2 - 1]["f"] if a2 > a1 else t0 + 0.3 * (b2 - b1)
            paso = (t1 - t0) / (b2 - b1)
            palabras += [{"t": round(t0 + k * paso, 3), "f": round(t0 + (k + 1) * paso, 3), "w": escritas[b1 + k]}
                         for k in range(b2 - b1)]
    return palabras


def palabras(guion: dict, wav: Path) -> list[dict]:
    from faster_whisper import WhisperModel

    segs, _ = WhisperModel("small", device="cpu", compute_type="int8").transcribe(
        str(wav), language="es", word_timestamps=True)
    oidas = [{"t": round(w.start, 3), "f": round(w.end, 3), "w": w.word.strip()} for s in segs for w in s.words]
    escritas = [w for e in guion["escenas"] for w in e["texto"].split()]
    return alinear(oidas, escritas)


def armar_props(guion: dict, tiempos: dict, lista: list[dict], audio: str | None) -> dict:
    """Solo lo que el render usa de cada escena."""
    campos = ("id", "texto", "visual", "camara", "etiquetas", "claves")
    return {"escenas": [{k: e[k] for k in campos if k in e} for e in guion["escenas"]],
            "tiempos": tiempos, "palabras": lista, "audio": audio}


def render(props: Path, salida: Path) -> None:
    salida.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["npx", "remotion", "render", "src/index.ts", "Tradicion", str(salida), f"--props={props}",
                    "--codec=h264", "--crf=20", "--timeout=120000", "--gl=angle"],
                   cwd=AQUI, check=True, shell=(sys.platform == "win32"))


def hoja(video: Path, salida: Path) -> None:
    subprocess.run([FFMPEG, "-v", "error", "-y", "-i", str(video), "-vf", "fps=1,scale=216:-1,tile=8x12",
                    "-frames:v", "1", str(salida)], check=True)


def main(argv: list[str]) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    slug = next(a for a in argv if not a.startswith("--"))
    guion = json.loads((ANDROID_IN / slug / "guion.json").read_text(encoding="utf-8"))
    publico = AQUI / "public" / slug
    inicio = time.time()
    tiempos = voz(guion, ANDROID_IN / slug / "voz_3d", publico / "voz.wav")
    print(f"voz lista: {tiempos['duracion']:.1f} s de audio, en {time.time() - inicio:.0f} s", flush=True)
    lista = palabras(guion, publico / "voz.wav")
    props = publico / "props.json"
    props.write_text(json.dumps(armar_props(guion, tiempos, lista, f"{slug}/voz.wav"), ensure_ascii=False),
                     encoding="utf-8")
    salida = AQUI / "out" / f"{slug}.mp4"
    antes = time.time()
    render(props, salida)
    print(f"render: {time.time() - antes:.0f} s", flush=True)
    if "--hoja" in argv:
        hoja(salida, AQUI / "out" / f"{slug}_hoja.jpg")
    print(f"RENDER {salida}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
