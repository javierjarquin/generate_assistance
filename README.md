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
        "prompt_ia": "prompt en inglés para Stable Diffusion"
      },
      "texto_en_pantalla": "opcional"
    }
  ]
}
```

`narracion` es la fuente de verdad para la alineación; `prompt_ia` genera la
ilustración (se le agrega `NARR_STYLE_SUFFIX` para estilo consistente).

## Sincronía audio-video

Las pausas entre planos y el solape de los crossfades se compensan
automáticamente (`render_timeline.py`): el inicio de cada plano en el video
coincide con el momento en que empiezas a decirlo en el audio.

## Validado

Pipeline completo verificado end-to-end con narración TTS de 55s
(`projects/demo-tts/`): 6/6 planos alineados, sincronía audio-video < 0.3s,
encode por hardware.
