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

**El gancho manda**: el plano 1 decide si el usuario se queda. Su `prompt_ia`
debe mostrar la promesa de la narración (si la voz dice "una torre con una luz
que se veía a 50 km", la imagen debe ser esa torre con esa luz — no una escena
genérica).

### Diccionario de datos

Campos que lee el sistema (los demás en el JSON se ignoran: son metadata de
producción para humanos). Referencia: `script_loader.py` y `entities/`.

#### `meta` (objeto, opcional)

| Campo | Tipo | Default | Uso |
|-------|------|---------|-----|
| `serie` | string | `""` | Informativo |
| `capitulo` | int | `0` | Informativo |
| `titulo` | string | `""` | **Título de gancho** (0–2.8s, caja de contraste) |
| `subtitulo` | string \| null | `null` | Informativo |
| `idioma` | string | `"es-MX"` | Sus 2 primeras letras fuerzan el idioma de whisper (`es`, `en`…) |

#### `planos[]` (array, **requerido**, ≥1)

| Campo | Tipo | Req. | Default | Uso |
|-------|------|:----:|---------|-----|
| `id` | string | ✅ | — | Identificador único (nombre de archivos: `<id>.png`, `<id>.mp4`). IDs duplicados = error |
| `narracion` | string | ✅ | — | Texto EXACTO a leer. Fuente de verdad de la alineación. No puede ser vacío |
| `visual` | objeto | ✅ | — | Ver abajo. Su `tipo` es obligatorio |
| `seccion` | string | | `""` | Informativo (gancho/desarrollo/cierre…) |
| `texto_en_pantalla` | string \| null | | `null` | Rótulo superior durante la ventana del plano (usa `\N` para salto de línea) |
| `audio` | objeto | | `{}` | Ver abajo |
| `inicio_aprox` | string \| null | | `null` | Solo planeación — **ignorado** (el tiempo real sale de la alineación) |
| `duracion_seg` | number \| null | | `null` | Solo planeación — **ignorado** (la duración real sale de la alineación) |

#### `planos[].visual` (objeto, **requerido**)

| Campo | Tipo | Req. | Default | Uso |
|-------|------|:----:|---------|-----|
| `tipo` | enum | ✅ | — | Debe ser uno de la lista de abajo. `archivo_historico` prioriza Wikimedia Commons al buscar medios reales; el resto no cambia el flujo |
| `prompt_ia` | string | | `""` | Prompt (en inglés) para Stable Diffusion. Se le concatena `NARR_STYLE_SUFFIX`. También se usa (recortado) como query de búsqueda de medios reales si no hay `busqueda_medios` |
| `descripcion` | string | | `""` | Texto humano; en el backend `placeholder` se dibuja como cartel |
| `busqueda_medios` | string \| null | | `null` | Query explícita para investigar medios reales (ver sección de abajo); si falta, se deriva de `prompt_ia` |
| `nota` | string \| null | | `null` | Informativo |
| `overlay` | string \| null | | `null` | Animación del plano (ver tabla) |
| `shake` | bool | | `false` | Sacudida de cámara (terremotos, impactos) |

**`visual.tipo`** (valores válidos): `imagen_ia`, `video_stock`, `animacion_3d`,
`mapa_animado`, `grafico_movimiento`, `cartel_texto`, `archivo_historico`.
Todo plano puede recibir una foto real (ver "Medios reales" abajo); si no se
encuentra un candidato relevante, se genera con IA desde `prompt_ia`. Un
`tipo` inválido aborta la carga del guion.

**`visual.overlay`** (sinónimos aceptados → efecto):

| Valor(es) | Efecto |
|-----------|--------|
| `niebla`, `fog`, `humo` | Niebla que se desplaza |
| `polvo`, `dust`, `particulas` | Partículas de polvo ascendentes |
| `lluvia`, `rain` | Lluvia cayendo |
| `burbujas`, `bubbles`, `submarino` | Burbujas ascendentes |
| `fuego`, `fire`, `llamas` | Parpadeo cálido (la imagen pulsa como iluminada por fuego) |

Cualquier otro valor se ignora (sin overlay).

#### `planos[].audio` (objeto, opcional)

| Campo | Tipo | Default | Uso |
|-------|------|---------|-----|
| `sfx` | string \| null | `null` | Dispara un efecto según palabras clave (ver tabla) |
| `musica` | string \| null | `null` | Reservado — la música global se toma de `assets/music.*` o se genera |

**`audio.sfx`** — el efecto se elige por palabra clave contenida en el texto:

| Si el texto contiene… | Efecto |
|-----------------------|--------|
| `ola`, `mar`, `agua`, `puerto` | Olas |
| `fuego`, `llama`, `hoguera`, `crepit` | Fuego crepitando |
| `terremoto`, `retumb`, `derrumb`, `temblor` | Retumbe grave |
| `viento`, `niebla`, `brisa` | Viento |
| `burbuja`, `submarino`, `buceo` | Burbujas |

Sin palabra clave reconocida, el plano va sin SFX (no falla).

> El movimiento de cámara (Ken Burns) no se configura por plano: se asigna
> automáticamente y, en planos con varias tomas, alterna entre ellas.

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

## Medios reales (antes de generar con IA)

Antes de mandar un plano a Stable Diffusion, la herramienta investiga si hay
una **foto real** que le sirva — para cualquier guion, no solo histórico o
documental. Un plano de ficción sin equivalente real simplemente no encuentra
candidatos y se genera con IA, igual que hoy.

- **Fuentes**: [Pexels](https://www.pexels.com/api/) (stock general, licencia
  libre) y [Wikimedia Commons](https://commons.wikimedia.org) (archivo
  público/histórico, sin API key). `visual.tipo: archivo_historico` prueba
  Wikimedia primero; el resto prueba Pexels primero.
- **Filtro de relevancia**: si el mejor resultado no tiene suficiente
  solapamiento de palabras clave con la búsqueda, se descarta — no se fuerza
  una foto real irrelevante solo porque el proveedor devolvió "algo"
  (`NARR_MEDIA_RELEVANCE_MIN_SCORE`).
- **Dónde queda todo**: `projects/<slug>/media/<plano_id>/` guarda los
  candidatos descargados y `media/manifest.json` registra elegido +
  descartados con licencia/autor/url (créditos para la descripción de
  YouTube). El elegido se copia a `images/<shot_id>.png`, el mismo archivo
  que usaría la generación IA — cero cambios al ensamblador.
- **Revisar antes de generar**: `poetry run narrator media <slug>` corre solo
  la investigación (requiere narración ya grabada/transcrita). Para forzar
  una foto a mano, coloca `media/<plano_id>/elegido.<ext>` — gana sobre
  cualquier búsqueda.
- **Audio real**: si `assets/music.*` no existe, busca en
  [Freesound](https://freesound.org/apiv2/apply) una pista ambiental; igual
  por cada tipo de SFX (`sfx/<kind>.mp3`) que el guion use. El mecanismo de
  "el archivo del usuario gana" de la cama de audio no cambia.
- **Activar**: `NARR_PEXELS_API_KEY` y `NARR_FREESOUND_API_KEY` (gratis,
  registro simple) en `.env`. Sin keys, Wikimedia sigue funcionando solo;
  `NARR_ENABLE_MEDIA_RESEARCH=0` apaga toda la capa.
- **Fuera de alcance por ahora**: clips de video stock reales (solo fotos) y
  música/SFX por plano (sigue siendo una pista global + SFX por categoría).

## Sincronía audio-video

Las pausas entre planos y el solape de los crossfades se compensan
automáticamente (`render_timeline.py`): el inicio de cada plano en el video
coincide con el momento en que empiezas a decirlo en el audio.

## Validado

Pipeline completo verificado end-to-end con narración real (`projects/demo/`):
6/6 planos alineados, sincronía < 0.3s, imágenes SD, karaoke, cama de audio a
-14 LUFS, multi-toma y CTA. También validado en 9:16 con `--vertical`.
