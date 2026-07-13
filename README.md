# Illustrated Narrator

Genera un video narrado con ilustraciones dinámicas a partir de un guion por
planos (JSON) y una grabación de audio continua. Transcribe el audio con
faster-whisper, alinea cada plano del guion contra los timestamps reales de lo
que dijiste, genera una ilustración por plano (Stable Diffusion vía
AUTOMATIC1111, o carteles placeholder para pruebas), anima cada imagen con
efecto Ken Burns, y ensambla todo con crossfades, subtítulos y tu audio.

## Requisitos

- Python 3.12 o 3.13, [Poetry](https://python-poetry.org/) y FFmpeg
- Opcional (imágenes IA reales): AUTOMATIC1111 WebUI corriendo con `--api`

## Instalación

```bash
poetry install
cp .env.example .env   # ajustar NARR_IMAGE_BACKEND=placeholder para probar sin A1111
```

## Uso

1. Crea `projects/<slug>/guion.json` (ver formato abajo; hay un ejemplo en
   `projects/demo/`).
2. Graba tu narración **leyendo los planos en orden, en una sola toma**, con
   pausas naturales entre planos. Guárdala como `projects/<slug>/narracion.wav`.
   - Si tu grabadora produce mp3/m4a, conviértelo:
     `ffmpeg -i grabacion.m4a projects/<slug>/narracion.wav`
   - No importa si no lees palabra por palabra: la alineación tolera
     desviaciones (umbral 50% de coincidencia por plano).
3. Genera:

```bash
poetry run narrator generate <slug>
poetry run narrator status <slug>    # ver estado por plano
```

El resultado queda en `projects/<slug>/final.mp4`. El estado se guarda en
`planos_alineados.json`: re-correr no repite transcripción ni imágenes ya
hechas (borra ese archivo o `images/`/`clips/` para forzar regeneración).

## Formato de guion.json

```json
{
  "meta": { "serie": "...", "capitulo": 1, "titulo": "...", "idioma": "es-MX" },
  "planos": [
    {
      "id": "p01",
      "seccion": "gancho",
      "narracion": "Texto EXACTO que vas a leer en este plano.",
      "visual": {
        "tipo": "imagen_ia",
        "descripcion": "para humanos",
        "prompt_ia": "prompt en inglés para Stable Diffusion",
        "overlay": "niebla",
        "shake": false
      },
      "audio": { "sfx": "olas de mar", "musica": "opcional" },
      "texto_en_pantalla": "opcional"
    }
  ]
}
```

`narracion` es la fuente de verdad para la alineación; `prompt_ia` genera la
ilustración (se le agrega `NARR_STYLE_SUFFIX` para estilo consistente).
`visual.overlay` (niebla/polvo/lluvia/burbujas/fuego) y `visual.shake` animan
el plano; `audio.sfx` dispara un efecto (olas/fuego/viento/terremoto/burbujas).

**El gancho manda**: el plano 1 decide si el usuario se queda. Su `prompt_ia`
debe mostrar la promesa de la narración (si la voz dice "una torre con una luz
que se veía a 50 km", la imagen debe ser esa torre con esa luz — no una escena
genérica).

## Estándares de retención (automáticos)

La herramienta aplica a CUALQUIER video, sin configurar nada:

- **Karaoke** palabra por palabra + **título de gancho** con caja de contraste
- **Audio a -14 LUFS** (estándar YouTube/Shorts) — un video callado pierde al espectador
- **Cambio visual cada ~4s**: los planos largos se parten en varias "tomas"
  (imágenes distintas del mismo tema) con corte seco — `retention_plan.py`
- **Transiciones cortas** (0.28s) + variadas, grading global
- **Tarjeta de cierre (CTA)** que invita a seguir — `NARR_CTA_TEXT`
- **Cama de audio** (música + SFX + whoosh) con ducking bajo la voz

Palancas de calidad de imagen: `NARR_SD_CHECKPOINT` (usa un modelo afinado en
vez del base SD 1.5) y `NARR_SD_WIDTH/HEIGHT` (16:9 nativo).

## Sincronía audio-video

Las pausas entre planos y el solape de los crossfades se compensan
automáticamente (`render_timeline.py`): el inicio de cada plano en el video
coincide con el momento en que empiezas a decirlo en el audio.

## Validado

Pipeline completo verificado end-to-end con narración real (`projects/demo/`):
6/6 planos alineados, sincronía < 0.3s, imágenes SD, karaoke, cama de audio a
-14 LUFS, multi-toma y CTA. También validado en 9:16 con `--vertical`.
