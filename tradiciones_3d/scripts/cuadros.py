"""Cuadros de prueba de un guion 3D, sin voz: le inventa tiempos (3 s por escena)
y saca un cuadro por escena con Remotion. Para afinar el estilo sin esperar un
render completo (unos 5 s por cuadro).

    python scripts/cuadros.py <etiqueta> <slug> [--solo=id1,id2] [--en=0.7]

Lee el guion de la carpeta del canal (variable ANDROID_IN, como render.py) y
deja out/cuadros/<etiqueta>_<id>.png y out/cuadros/<etiqueta>_hoja.jpg.
"""

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import render  # noqa: E402  -- el mismo armado de props que usa el video

DUR = 3.0


def main(argv: list[str]) -> int:
    args = [a for a in argv if not a.startswith("--")]
    opciones = dict(a[2:].split("=", 1) for a in argv if a.startswith("--") and "=" in a)
    etiqueta, slug = args[0], args[1]
    solo = opciones["solo"].split(",") if "solo" in opciones else None
    donde = float(opciones.get("en", 0.7))
    guion = json.loads((render.ANDROID_IN / slug / "guion.json").read_text(encoding="utf-8"))
    marcas, palabras, t = [], [], 0.0
    for e in guion["escenas"]:
        marcas.append({"id": e["id"], "ini": round(t, 2), "fin": round(t + DUR, 2)})
        ws = e["texto"].split()
        palabras += [{"t": round(t + i * DUR / len(ws), 3), "f": round(t + (i + 1) * DUR / len(ws), 3), "w": w}
                     for i, w in enumerate(ws)]
        t += DUR
    salida = render.AQUI / "out" / "cuadros"
    salida.mkdir(parents=True, exist_ok=True)
    props = salida / f"_{etiqueta}.props.json"
    props.write_text(json.dumps(render.armar_props(guion, {"duracion": t, "escenas": marcas}, palabras, None),
                                ensure_ascii=False), encoding="utf-8")
    pngs = []
    for m in marcas:
        if solo and m["id"] not in solo:
            continue
        png = salida / f"{etiqueta}_{m['id']}.png"
        subprocess.run(["npx", "remotion", "still", "src/index.ts", "Tradicion", str(png), f"--props={props}",
                        f"--frame={int((m['ini'] + DUR * donde) * 30)}", "--gl=angle", "--timeout=120000", "--log=error"],
                       cwd=render.AQUI, check=True, shell=(sys.platform == "win32"))
        pngs.append(png)
    hoja = salida / f"{etiqueta}_hoja.jpg"
    cols = min(5, len(pngs))
    if len(pngs) > 1:
        filtro = "".join(f"[{i}:v]scale=432:-1[v{i}];" for i in range(len(pngs)))
        filtro += "".join(f"[v{i}]" for i in range(len(pngs))) + f"xstack=inputs={len(pngs)}:layout=" + "|".join(
            f"{(i % cols) * 432}_{(i // cols) * 768}" for i in range(len(pngs))) + ":fill=white[o]"
    else:
        filtro = "[0:v]scale=432:-1[o]"
    entradas = [x for p in pngs for x in ("-i", str(p))]
    subprocess.run([render.FFMPEG, "-v", "error", "-y", *entradas, "-filter_complex", filtro, "-map", "[o]",
                    "-frames:v", "1", str(hoja)], check=True)
    print(hoja)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
