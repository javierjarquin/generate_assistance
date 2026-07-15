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
  Punch-in por toma. **Escalada de ritmo**: hacia el 75% del video el límite
  de segundos por toma baja gradualmente (más cortes) y desde el 85% hay un
  piso de energía de movimiento — el clímax no se siente plano.
- **Parallax 2.5D** (`parallax.py` + Depth-Anything V2 ONNX en CPU): el frente
  se mueve más que el fondo. **Selectivo**: si la profundidad es plana cae a
  Ken Burns.
- **Multi-toma** en planos largos (corte seco), transiciones cortas + variadas,
  cortes casi-secos en los primeros 5s, grading global.
- **Audio**: cama de música + SFX por plano + whoosh, con ducking; **loudnorm
  a -14 LUFS**; **voz procesada** (EQ + compresión + de-ess); **música real**
  desde `assets/music.<ext>` (acepta mp3/wav/m4a/ogg/mp4/mkv…).
- **Calidad de imagen**: recorte de marcos/bordes (`image_cleaner.py`), incluida
  la esquina en L aislada (se rellena por inpainting, no se recorta).
- **Consistencia de estilo** (`NARR_STYLE_MODE`: auto/ilustracion/realista/
  unificado).
- **Medios reales**: fotos (Pexels + Wikimedia) **y video real** (Pexels Video)
  antes de generar con IA — la investigación automática elige el candidato de
  mejor relevancia sea foto o video, sin tocar `guion.json`.
- **Checkpoint SD**: DreamShaper 8 descargado y activo (`NARR_SD_CHECKPOINT`).
  Mirror sin login que sí funcionó: `https://huggingface.co/digiplay/DreamShaper_8/resolve/main/dreamshaper_8.safetensors`.
- **Identidad de marca** (solo texto/paleta por ahora): tarjeta de intro
  configurable (`NARR_BRAND_NAME`), color de acento centralizado
  (`NARR_BRAND_ACCENT_COLOR`, aplica al karaoke) — el mecanismo ya soporta
  agregar un logo PNG más adelante sin rehacer nada.
- Pipeline **resumible** (transcript.json, planos_alineados.json). El demo en
  `projects/demo` conserva imágenes → se re-renderiza **sin GPU** (~90s CPU).

## Pendiente

- **Logo de marca real**: cuando haya un PNG, engancharlo vía `NARR_BRAND_LOGO_PATH`
  (el parámetro `logo_path` ya existe en `render_intro_card`, falta solo la
  variable de entorno + wiring en `container.py`).
- Menor: revisar los umbrales de detección de esquina en L
  (`_CORNER_CONTENT_FRAC`/`_CORNER_MIN_FRAC`/`_CORNER_MAX_FRAC` en
  `image_cleaner.py`) contra una imagen real de escaneo — se calibraron con
  casos sintéticos.

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
