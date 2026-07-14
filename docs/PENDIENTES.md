# Illustrated Narrator — Pendientes y checkpoint

Estado al 2026-07-14. Este documento permite retomar el proyecto en otra
máquina sin perder contexto.

## Ya hecho (no repetir)

- Karaoke / captions estilo Shorts (chunks 2-3 palabras con pop, Arial Black,
  borde+sombra, **sin caja**), palabra hablada resaltada en amarillo, título en
  blanco (jerarquía de color).
- **Chunking gramatical**: un chunk no termina en palabra función.
- **Gancho de tensión** (`meta.gancho`) que se envuelve solo; título con pop.
- **Tarjeta de cierre (CTA)** configurable.
- **Movimiento por contenido** (`motion_profile.py`): perfiles calm/normal/
  energetic/impact; se infiere del contenido o se fija con `visual.motion`.
  Punch-in por toma.
- **Parallax 2.5D** (`parallax.py` + Depth-Anything V2 ONNX en CPU): el frente
  se mueve más que el fondo. **Selectivo**: si la profundidad es plana cae a
  Ken Burns.
- **Multi-toma** en planos largos (corte seco), transiciones cortas + variadas,
  cortes casi-secos en los primeros 5s, grading global.
- **Audio**: cama de música + SFX por plano + whoosh, con ducking; **loudnorm
  a -14 LUFS**; **voz procesada** (EQ + compresión + de-ess); **música real**
  desde `assets/music.<ext>` (acepta mp3/wav/m4a/ogg/mp4/mkv…).
- **Calidad de imagen**: recorte de marcos/bordes (`image_cleaner.py`).
- **Consistencia de estilo** (`NARR_STYLE_MODE`: auto/ilustracion/realista/
  unificado).
- **Medios reales** (Pexels + Wikimedia) antes de generar con IA.
- Pipeline **resumible** (transcript.json, planos_alineados.json). El demo en
  `projects/demo` conserva imágenes → se re-renderiza **sin GPU** (~90s CPU).

## Pendiente (lista crítica, por impacto)

1. **Checkpoint SD mejor** — el mayor salto de calidad de imagen que falta.
   El base SD 1.5 obedece mal los prompts. El soporte ya existe
   (`NARR_SD_CHECKPOINT`, vía `override_settings`); falta el modelo:
   - Descargar un checkpoint afinado (p. ej. **DreamShaper 8**, **Realistic
     Vision**) de civitai.com (la descarga directa de HuggingFace daba 403).
   - Ponerlo en `tools/stable-diffusion-webui/models/Stable-diffusion/`.
   - Poner su nombre en `NARR_SD_CHECKPOINT`.

2. **B-roll de video real** (Pexels Video API) — alternar imágenes fijas
   animadas con clips de video reales en algunos planos. El salto que más
   acerca a "profesional". Ya hay puertos de stock media que se pueden extender
   a video.

3. **Escalada de ritmo** — acelerar los cortes hacia el clímax en vez de un
   ritmo parejo de principio a fin.

4. **Identidad de marca** — intro/outro reconocible, logo, paleta.

5. Menor: en imágenes que son escaneo de libro con texto impreso queda una
   esquina blanca (el recorte rectangular no quita regiones en L). Solución
   real = mejor fuente de imagen (punto 1).

## Setup en otra PC

1. **Python 3.12** (3.14 no tiene wheels de numba/ctranslate2). Poetry.
2. `poetry install` (trae typer, faster-whisper, pillow, requests, **onnxruntime,
   opencv-python-headless, numpy** para parallax).
3. **FFmpeg** en PATH (o `NARR_FFMPEG_PATH`).
4. **Modelo de profundidad** (parallax): descargar Depth-Anything V2 small ONNX
   a `models/depth_anything_v2_vits.onnx` (~99 MB, va en `.gitignore`):
   `https://huggingface.co/onnx-community/depth-anything-v2-small/resolve/main/onnx/model.onnx`
   Sin el modelo, el parallax cae a Ken Burns (no se rompe).
5. **AUTOMATIC1111** para imágenes IA (opcional; con `NARR_IMAGE_BACKEND=placeholder`
   se prueba sin él). Arrancar con `--api`. En GPUs de la familia GTX 16xx /
   Turing de gama baja, fp16 produce NaN → usar `--api --medvram --no-half
   --no-half-vae`. Si el clone falla por el repo borrado de Stability-AI:
   `set STABLE_DIFFUSION_REPO=https://github.com/w-e-w/stablediffusion.git`.
6. Copiar `.env.example` a `.env` y ajustar.

## Uso rápido

```bash
# probar sin A1111 (carteles) y sin GPU
NARR_IMAGE_BACKEND=placeholder poetry run narrator generate <slug>

# con imágenes IA (A1111 corriendo) + parallax
poetry run narrator generate <slug>

# vertical 9:16 para Shorts/Reels
poetry run narrator generate <slug> --vertical
```

Un proyecto es `projects/<slug>/` con `guion.json` + `narracion.wav`. Ver el
formato completo de `guion.json` en el README (diccionario de datos).
