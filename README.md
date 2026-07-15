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
| `titulo` | string | `""` | Título; se usa como gancho si no hay `gancho` |
| `gancho` | string \| null | `null` | **Frase de tensión** que aparece en 0-2.6s (una pregunta/promesa que engancha, no solo el tema). Se envuelve sola si es larga |
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
| `shake` | bool | | `false` | Sacudida de cámara (equivale a `motion: impact`) |
| `motion` | enum \| null | | `null` (inferido) | Energía del movimiento de cámara: `calm`, `normal`, `energetic`, `impact`. Si falta se **infiere** del contenido (shake, overlay de fuego, palabras de impacto/acción en la narración) |

**`visual.tipo`** (valores válidos): `imagen_ia`, `video_stock`, `animacion_3d`,
`mapa_animado`, `grafico_movimiento`, `cartel_texto`, `archivo_historico`.
Todo plano puede recibir una foto o un clip de **video real** (ver "Medios
reales" abajo); si no se encuentra un candidato relevante, se genera con IA
desde `prompt_ia`. No hace falta fijar `video_stock` a mano — la elección
entre foto/video/IA es automática por relevancia. Un `tipo` inválido aborta
la carga del guion.

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

> El sentido del Ken Burns (pan/zoom) se asigna automáticamente y alterna entre
> tomas; su **energía** la fija `visual.motion` (o se infiere del contenido).

## Modo mascota (personaje que presenta)

Con `NARR_NARRACION=mascota` y `NARR_MASCOTA_PATH=ruta/a/tu/mascota`, un
personaje aparece en una esquina y **presenta** el video: la boca se mueve con
la voz (lip-sync por volumen) y hace gestos (saluda, señala, camina, salta,
festeja) según lo que pasa en el video. Da la sensación de que la voz sale de
la mascota.

> La herramienta **no crea la mascota** — tú la dibujas y armas la carpeta con
> lo que se describe aquí; la herramienta la anima y la coloca en el video.

### Manual de la carpeta de la mascota

Cada "acción" es una animación. Puedes entregarla de dos formas:

- **Carpeta con PNGs numerados**: `talk/00.png, talk/01.png, …` (en orden), o
- **Un archivo animado**: `talk.gif`, `talk.png` (APNG), `talk.webp` o
  `talk.webm`/`talk.mov` (con canal alfa).

Requisitos de los sprites:
- **Fondo transparente** (PNG/GIF/WebM con alfa). Sin fondo de color.
- **Mismo lienzo** en todas las acciones (misma resolución) para que no salte.
- Personaje **de cuerpo entero**, mirando al frente, **centrado horizontal y
  con los pies abajo** (se ancla al piso de la esquina).
- Alto recomendado 512–1024px (se escala a `NARR_MASCOTA_HEIGHT_FRAC` del video).

### Acciones (qué necesito y cuándo las uso)

| Acción | ¿Obligatoria? | Cuándo la pone la herramienta |
|--------|:-------------:|-------------------------------|
| `talk` | ✅ | Base mientras narra un plano. **La boca debe moverse** en esta animación (es la que se ve al hablar) |
| `idle` | ✅ | Pausas/silencios y relleno. Boca cerrada, respira/parpadea |
| `wave` | opcional | Saludo al entrar el primer plano |
| `walk` | opcional | Entra caminando en las transiciones de plano |
| `point` | opcional | Señala (énfasis) cada ciertos planos |
| `jump` | opcional | Salta en los planos de mucha energía (impacto/acción) |
| `celebrate` | opcional | Festeja durante la tarjeta de cierre (CTA) |

Si falta una acción opcional, se cae a `talk`/`idle` (no se rompe). El lip-sync
funciona así: durante `talk`, si la voz baja del umbral la boca se cierra
(`idle`); cuando hay voz vuelve a `talk`. Por eso `talk` debe traer la boca
abierta/moviéndose en el arte y `idle` la boca cerrada.

Ejemplo de carpeta mínima:

```
mi_mascota/
├── talk/     (o talk.gif)     # hablando, boca en movimiento  [OBLIGATORIA]
├── idle/     (o idle.gif)     # quieta, boca cerrada           [OBLIGATORIA]
├── wave/     (o wave.gif)     # saluda                          (opcional)
├── walk/     ...              # camina                          (opcional)
├── point/    ...              # señala                          (opcional)
├── jump/     ...              # salta                           (opcional)
└── celebrate/ ...             # festeja                         (opcional)
```

Config: `NARR_MASCOTA_POS` (esquina), `NARR_MASCOTA_HEIGHT_FRAC` (tamaño),
`NARR_MASCOTA_FPS` (velocidad de la animación), `NARR_MASCOTA_VOICE_THRESHOLD`
(sensibilidad del lip-sync).

## Estándares de retención (automáticos)

La herramienta aplica a CUALQUIER video, sin configurar nada. La referencia de
qué son y de dónde salen está en `domain/services/retention_standards.py`:

- **Captions estilo Shorts/CapCut** (no PowerPoint): chunks de 2-3 palabras que
  entran con un **pop** de escala, fuente gruesa con borde+sombra (sin caja),
  palabra hablada resaltada en amarillo — `ass_writer.py`
- **Título de gancho** con pop inmediato en <2.6s (sin caja)
- **Movimiento por contenido**: el Ken Burns deja de ser uniforme — impacto/
  terremoto = zoom rápido + sacudida; calma = deriva lenta — `motion_profile.py`
- **Punch-in** al entrar cada toma (reset de atención)
- **Cambio visual cada 2-4s**: planos largos partidos en varias tomas con corte
  seco — `retention_plan.py`
- **Escalada de ritmo**: a partir del 75% del video el límite de segundos por
  toma baja gradualmente (más cortes hacia el clímax) y desde el 85% hay un
  piso de energía de movimiento — el tramo final no se siente plano —
  `retention_plan.py` (`max_shot_seconds_for_progress`, `motion_floor_for_progress`)
- **Sin dissolves en los primeros 5s** (cortes secos que "despiertan")
- **Audio a -14 LUFS** (estándar YouTube/Shorts) — un video callado se pierde
- **Tarjeta de cierre (CTA)** que invita a seguir — `NARR_CTA_TEXT`
- **Cama de audio** (música + SFX + whoosh) con ducking bajo la voz

Palancas de calidad de imagen: `NARR_SD_CHECKPOINT` (usa un modelo afinado en
vez del base SD 1.5 — [DreamShaper 8](https://huggingface.co/digiplay/DreamShaper_8)
es un buen default gratis y sin login) y `NARR_SD_WIDTH/HEIGHT` (16:9 nativo).

### Parallax 2.5D (movimiento 3D real)

En vez del Ken Burns plano, cada imagen recibe **movimiento con profundidad**:
se estima un mapa de profundidad (Depth-Anything V2 small, ONNX en CPU, ~0.6s
por imagen) y se hace un warp por-pixel donde el frente se desplaza más que el
fondo. Da la sensación de un video generado con IA. Verificado: el frente se
mueve ~7.5x más que el fondo.

- Se activa con `NARR_PARALLAX=1` (por defecto) y el modelo en
  `models/depth_anything_v2_vits.onnx`. Sin modelo, cae a Ken Burns.
- La energía la marca el mismo `visual.motion` (impact = cámara más agresiva).
- Costo: ~1.5s de render por segundo de clip (CPU). El resto del pipeline es
  resumible, así que solo se paga al re-renderizar clips.

### Consistencia de estilo

Mezclar fotos reales con ilustraciones IA se ve amateur. `NARR_STYLE_MODE`:

- `ilustracion` — todo con IA (mismo `NARR_STYLE_SUFFIX`), sin fotos reales
- `realista` — prioriza fotos reales
- `unificado` — mezcla pero aplica un grade común fuerte para cohesionar
- `auto` — comportamiento por defecto

## Medios reales (antes de generar con IA)

Antes de mandar un plano a Stable Diffusion, la herramienta investiga si hay
una **foto o un clip de video real** que le sirva — para cualquier guion, no
solo histórico o documental. Un plano de ficción sin equivalente real
simplemente no encuentra candidatos y se genera con IA, igual que hoy.

- **Fuentes**: [Pexels](https://www.pexels.com/api/) fotos y
  [Pexels Video](https://www.pexels.com/api/) (misma key), y
  [Wikimedia Commons](https://commons.wikimedia.org) (archivo
  público/histórico, sin API key). `visual.tipo: archivo_historico` prueba
  Wikimedia primero; el resto prueba Pexels primero. **Foto y video compiten
  por relevancia entre sí** — no hay que fijar `video_stock` a mano, el que
  mejor puntúe gana (video ≤40s, se recorta a la duración de la toma y se
  repite en loop si hace falta).
- **Filtro de relevancia**: si el mejor resultado no tiene suficiente
  solapamiento de palabras clave con la búsqueda, se descarta — no se fuerza
  un resultado irrelevante solo porque el proveedor devolvió "algo"
  (`NARR_MEDIA_RELEVANCE_MIN_SCORE`).
- **Dónde queda todo**: `projects/<slug>/media/<plano_id>/` guarda los
  candidatos descargados y `media/manifest.json` registra elegido +
  descartados con licencia/autor/url/tipo (créditos para la descripción de
  YouTube). La foto elegida se copia a `images/<shot_id>.png` (mismo archivo
  que usaría la generación IA); el video elegido va a
  `media/videos/<shot_id>.mp4` — cero cambios al resto del ensamblador, que
  resuelve automáticamente cuál usar.
- **Revisar antes de generar**: `poetry run narrator media <slug>` corre solo
  la investigación (requiere narración ya grabada/transcrita). Para forzar
  un medio a mano, coloca `media/<plano_id>/elegido.<ext>` (`.mp4` para
  forzar video) — gana sobre cualquier búsqueda.
- **Audio real**: si `assets/music.*` no existe, busca en
  [Freesound](https://freesound.org/apiv2/apply) una pista ambiental; igual
  por cada tipo de SFX (`sfx/<kind>.mp3`) que el guion use. El mecanismo de
  "el archivo del usuario gana" de la cama de audio no cambia.
- **Activar**: `NARR_PEXELS_API_KEY` y `NARR_FREESOUND_API_KEY` (gratis,
  registro simple) en `.env`. Sin keys, Wikimedia sigue funcionando solo;
  `NARR_ENABLE_MEDIA_RESEARCH=0` apaga toda la capa,
  `NARR_MEDIA_ENABLE_VIDEO=0` apaga solo el B-roll de video (deja fotos).
- **Fuera de alcance por ahora**: música/SFX por plano (sigue siendo una
  pista global + SFX por categoría).

## Identidad de marca

Tarjeta de apertura configurable y color de acento centralizado (hoy solo
texto — el logo queda para cuando haya un PNG):

- `NARR_BRAND_NAME` — si se fija, antepone una tarjeta de intro con ese
  nombre (mismo look que la tarjeta de cierre) y retrasa automáticamente
  narración, captions y cortes de la cama de audio lo que haga falta para
  que todo siga sincronizado. Vacío = sin intro (comportamiento de siempre).
- `NARR_BRAND_ACCENT_COLOR` — color de acento en formato `#RRGGBB` (aplica
  hoy a la palabra resaltada del karaoke). Default `#FFE800`, el mismo
  amarillo que ya tenía la herramienta — no cambia nada si no se toca.
- `NARR_BRAND_INTRO_DURATION` — segundos de la tarjeta de intro (default `2.0`).

## Sincronía audio-video

Las pausas entre planos y el solape de los crossfades se compensan
automáticamente (`render_timeline.py`): el inicio de cada plano en el video
coincide con el momento en que empiezas a decirlo en el audio.

## Validado

Pipeline completo verificado end-to-end con narración real (`projects/demo/`):
6/6 planos alineados, sincronía < 0.3s, imágenes SD, karaoke, cama de audio a
-14 LUFS, multi-toma y CTA. También validado en 9:16 con `--vertical`.
