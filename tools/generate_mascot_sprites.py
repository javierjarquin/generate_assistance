"""Genera los sprites de la mascota (Balam) a partir de los PROMPT.txt de cada
carpeta de expresion, pegandole directo a la API de AUTOMATIC1111.

No es parte del pipeline de narracion (ese solo hace txt2img por plano) --
esto es una herramienta de preparacion de assets, de un solo uso por proyecto:
- Genera "idle" primero como referencia (txt2img, seed fija).
- El resto de expresiones usa img2img sobre esa referencia. Probado
  empiricamente: denoise 0.5 (el que sugeria originalmente cada PROMPT.txt)
  deja el resultado CASI IDENTICO a idle -- ninguna pose distinta se nota
  (ni "walk" en zancada ni "jump" en el aire). Hace falta 0.85 para que la
  pose realmente cambie, conservando igual el personaje (mismo prompt +
  misma referencia). Solo el parpadeo de "idle" (variacion minima de la
  MISMA pose) usa el denoise bajo.
- Es resumible: si el PNG de una toma ya existe en disco, no se regenera
  (asi se puede corregir/relanzar solo lo que falta sin repetir lo bueno).
- Quita el fondo con GrabCut (mucho mas robusto que un flood-fill por color
  cuando el fondo tiene bajo contraste con partes claras del personaje) y
  guarda PNG con alfa real.

Uso:
    poetry run python tools/generate_mascot_sprites.py projects/Capitulo1/mascota
"""

from __future__ import annotations

import base64
import re
import sys
from pathlib import Path

import cv2
import numpy as np
import requests

A1111_BASE_URL = "http://127.0.0.1:7860"
CHECKPOINT = "dreamshaper_8.safetensors"
STEPS = 30
CFG_SCALE = 6.5
SAMPLER = "DPM++ 2M Karras"
SIZE = 1024
SEED = 246813579
DENOISE_FRAME_VARIANT = 0.5  # variacion sutil de la MISMA pose (parpadeo de idle)
DENOISE_POSE = 0.85          # pose realmente distinta (todo lo demas)
TIMEOUT = 900

# DreamShaper a veces mete un logo/marca de agua garabateado en una esquina, o
# duplica el personaje (dos crias en vez de una). Se refuerza prompt/negative
# de cada PROMPT.txt (que ya trae "watermark, signature, multiple characters"
# pero no siempre alcanza) en vez de tocar los 12 archivos.
_EXTRA_POSITIVE = ", solo, single character, only one baby jaguar, one subject"
_EXTRA_NEGATIVE = (
    ", (watermark:1.4), (logo:1.4), (text:1.3), (signature:1.3), brand logo, "
    "gibberish text, asian text, chinese text, japanese text, letters, writing, "
    "(two characters:1.4), (duplicate:1.3), twins, pair, group, second character, "
    "side by side, multiple animals"
)

# Orden: idle primero (es la referencia), talk segundo (obligatoria), el resto
# alfabetico. Cada valor es (n_frames, sufijo_para_frame_1_si_aplica, denoise).
EXPRESSIONS: dict[str, tuple[int, str, float]] = {
    "idle": (2, ", eyes gently closed in a slow blink", DENOISE_FRAME_VARIANT),
    "talk": (2, ", mouth half-open mid-word, different mouth shape", DENOISE_POSE),
    "walk": (2, ", opposite leg forward, other arm swinging, mirrored stride", DENOISE_POSE),
    "wave": (1, "", DENOISE_POSE),
    "point": (1, "", DENOISE_POSE),
    "think": (1, "", DENOISE_POSE),
    "surprised": (1, "", DENOISE_POSE),
    "scared": (1, "", DENOISE_POSE),
    "sad": (1, "", DENOISE_POSE),
    "laugh": (1, "", DENOISE_POSE),
    "jump": (1, "", DENOISE_POSE),
    "celebrate": (1, "", DENOISE_POSE),
}


def parse_prompt_file(path: Path) -> tuple[str, str]:
    text = path.read_text(encoding="utf-8")
    prompt_match = re.search(r"PROMPT:\s*\n(.+?)\n\s*\n", text, re.DOTALL)
    negative_match = re.search(r"NEGATIVE:\s*\n(.+?)(\n\s*\n|\Z)", text, re.DOTALL)
    if not prompt_match:
        raise ValueError(f"No se encontro PROMPT: en {path}")
    prompt = prompt_match.group(1).strip().replace("\n", " ")
    negative = negative_match.group(1).strip().replace("\n", " ") if negative_match else ""
    return prompt + _EXTRA_POSITIVE, negative + _EXTRA_NEGATIVE


def _txt2img(session: requests.Session, prompt: str, negative: str) -> bytes:
    payload = {
        "prompt": prompt,
        "negative_prompt": negative,
        "width": SIZE,
        "height": SIZE,
        "steps": STEPS,
        "cfg_scale": CFG_SCALE,
        "sampler_name": SAMPLER,
        "seed": SEED,
        "override_settings": {"sd_model_checkpoint": CHECKPOINT},
        "override_settings_restore_afterwards": False,
    }
    resp = session.post(f"{A1111_BASE_URL}/sdapi/v1/txt2img", json=payload, timeout=TIMEOUT)
    resp.raise_for_status()
    images = resp.json().get("images")
    if not images:
        raise RuntimeError(f"A1111 no devolvio imagenes para: {prompt[:80]}")
    return base64.b64decode(images[0])


def _img2img(
    session: requests.Session, prompt: str, negative: str, init_png: bytes, denoise: float
) -> bytes:
    init_b64 = base64.b64encode(init_png).decode("ascii")
    payload = {
        "init_images": [init_b64],
        "prompt": prompt,
        "negative_prompt": negative,
        "width": SIZE,
        "height": SIZE,
        "steps": STEPS,
        "cfg_scale": CFG_SCALE,
        "sampler_name": SAMPLER,
        "seed": SEED,
        "denoising_strength": denoise,
        "override_settings": {"sd_model_checkpoint": CHECKPOINT},
        "override_settings_restore_afterwards": False,
    }
    resp = session.post(f"{A1111_BASE_URL}/sdapi/v1/img2img", json=payload, timeout=TIMEOUT)
    resp.raise_for_status()
    images = resp.json().get("images")
    if not images:
        raise RuntimeError(f"A1111 no devolvio imagenes (img2img) para: {prompt[:80]}")
    return base64.b64decode(images[0])


def remove_background(png_bytes: bytes) -> np.ndarray:
    """Quita el fondo con GrabCut, asumiendo el personaje centrado (el mismo
    encuadre que pide el prompt: "full body, centered, feet at the bottom").
    Mucho mas robusto que un flood-fill por color cuando el fondo tiene bajo
    contraste con partes claras del personaje (belly/muzzle crema) -- un
    flood-fill puede "filtrarse" a traves de ese borde y comerse el sujeto
    entero, cosa que ya paso en la primera prueba de esta herramienta."""
    arr = np.frombuffer(png_bytes, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    h, w = img.shape[:2]

    mask = np.zeros((h, w), np.uint8)
    bgd_model = np.zeros((1, 65), np.float64)
    fgd_model = np.zeros((1, 65), np.float64)
    margin_x, margin_y = int(w * 0.06), int(h * 0.04)
    rect = (margin_x, margin_y, w - 2 * margin_x, h - 2 * margin_y)
    cv2.grabCut(img, mask, rect, bgd_model, fgd_model, 5, cv2.GC_INIT_WITH_RECT)

    alpha = np.where(
        (mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0
    ).astype(np.uint8)
    # suaviza el borde del recorte para que no quede dentado
    alpha = cv2.GaussianBlur(alpha, (5, 5), 0)
    bgra = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
    bgra[:, :, 3] = alpha
    return bgra


def main(mascota_dir: Path) -> None:
    session = requests.Session()
    resp = session.get(f"{A1111_BASE_URL}/sdapi/v1/options", timeout=10)
    resp.raise_for_status()
    print(f"A1111 OK. Generando en {mascota_dir}...")

    reference_raw: bytes | None = None
    order = list(EXPRESSIONS.keys())

    for name in order:
        folder = mascota_dir / name
        prompt_file = folder / "PROMPT.txt"
        if not prompt_file.exists():
            print(f"[{name}] sin PROMPT.txt, se salta")
            continue
        n_frames, frame1_suffix, denoise = EXPRESSIONS[name]
        base_prompt, negative = parse_prompt_file(prompt_file)

        for i in range(n_frames):
            dest = folder / f"{i:02d}.png"
            if dest.exists():
                print(f"[{name}] frame {i} ya existe, se conserva")
                if reference_raw is None:
                    reference_raw = dest.read_bytes()
                continue

            prompt = base_prompt if i == 0 else f"{base_prompt}{frame1_suffix}"
            print(f"[{name}] frame {i} -> {dest}")

            if reference_raw is None:
                raw = _txt2img(session, prompt, negative)
                reference_raw = raw  # idle frame 0 es la referencia de ahora en más
            else:
                raw = _img2img(session, prompt, negative, reference_raw, denoise)

            bgra = remove_background(raw)
            dest.parent.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(str(dest), bgra)
            print(f"[{name}] frame {i} listo ({bgra.shape[1]}x{bgra.shape[0]})")

    print("Listo. Revisa los PNG generados antes de usarlos (algunos pueden necesitar reintento).")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: poetry run python tools/generate_mascot_sprites.py <carpeta_mascota>")
        raise SystemExit(1)
    main(Path(sys.argv[1]))
