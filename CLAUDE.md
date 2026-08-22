# CLAUDE.md

## Qué es este proyecto

`illustrated-narrator` genera videos narrados (verticales/horizontales) a partir de un `guion.json` (guion por planos) + un audio de narración real. Para las imágenes/video de cada plano investiga medios reales antes de considerar cualquier otra fuente: Pexels (fotos+video) y Wikimedia Commons primero, Openverse como respaldo; y como último recurso automático (`_proper_noun_fallback`, con nombres propios de la narración, para CUALQUIER plano) también prueba artículos de Wikipedia (imágenes de contenido embebidas) y NASA Images. Usa Whisper para transcribir/alinear la narración y ffmpeg para el ensamblado final.

## Config fija — no proponer cambiarla

- **Cero IA de imágenes.** Cada plano se resuelve con medio real investigado (`NARR_ENABLE_MEDIA_RESEARCH=1`). Nunca generar con Stable Diffusion/A1111 como "solución" a un plano sin match.
- Si un plano se queda sin medio real, el capítulo se reporta como fallo — no se completa con IA ni con un cartel de relleno.
- No propongas reactivar la generación IA como atajo cuando un plano no encuentra medio real. El camino es mejorar la búsqueda (ver más abajo) o dejar que el usuario lo revise/reemplace a mano.

## Dos flujos distintos

1. **Producción en lote** (`tools/procesar_lote.ps1`) — corre sola, desatendida, contra `C:\Android_in` / `C:\Android_out`. No la toques salvo que te lo pidan explícitamente.
2. **Refinamiento manual** (lo que sigue aplica acá) — el usuario retoma una sesión de Claude Code (directo o vía el bot de Telegram) para generar/ajustar UN capítulo puntual.

## Si esta sesión la disparó el bot de Telegram (`claude -p`)

El único propósito de estas sesiones es generar/ajustar videos del canal
usando las herramientas que ya existen en este workspace (`tts-kokoro`,
`illustrated-narrator`, `Android_in`/`Android_out`) — no conversación
general, no tareas fuera de este pipeline.

Cada mensaje del bot corre como un proceso `claude -p` NUEVO y corto que
se cierra en cuanto responde — no es una sesión interactiva de larga vida.

**El bot NO invoca a Claude para recolectar archivos.** El usuario manda
el `guion.json` y las imágenes con `/nuevovideo` primero — el bot los
guarda directo en disco (puente puro, sin LLM de por medio). La ÚNICA
vez que se dispara esta sesión es con el comando `/generar`, y para
entonces el `guion.json` y cualquier imagen manual YA están en disco,
listos para usarse — no hay que esperar a que "llegue" nada más ni pedir
que se reenvíe un adjunto.

**Nunca correr `tts_kokoro.cli`, `narrator generate`, ni ningún paso largo
del pipeline con `run_in_background`/en segundo plano.** Si el proceso
`-p` termina de responder antes de que esa tarea en segundo plano acabe,
la notificación de "ya terminó" no tiene a qué sesión llegarle en el
siguiente mensaje — queda huérfana, y el usuario nunca se entera del
resultado real (visto en la práctica: tareas marcadas "stopped, no
completion record found"). Correr TODO en foreground/bloqueante dentro
del mismo turno, aunque tarde varios minutos — el bot ya espera hasta
60 minutos por una respuesta.

## Cuando el bot te escala un capítulo (el mensaje empieza con "El pipeline automático...")

El bot corre `pipeline.py` (código puro, sin Claude) ANTES de invocarte, y
solo te llama si algo quedó ambiguo. Para cuando lees esto, YA se hizo —
sin gastar un token tuyo — todo esto:

- Audio generado con `tts-kokoro`
- Proyecto armado en `illustrated-narrator/projects/<slug>/`
- Logo del canal copiado a `media/p00/elegido_1.*` (si existe)
- **Imágenes manuales que mandó el usuario por Telegram, ya copiadas a
  `elegido_N.*`** — esto es siempre mecánico, nunca requiere que vos las
  toques, revises o reemplaces. Si el usuario mandó una foto para un
  plano, esa foto YA está puesta; no la analices ni la sustituyas por una
  búsqueda.
- Al menos 1 corrida de `narrator generate`, con 2 reintentos automáticos
  (por país/lugar incoherente, ver `media_check.py` en el bot) ya
  agotados.

**Lo único que tenés que hacer es lo que el mensaje de escalación
describe como pendiente** (la lista de tomas `pais_incoherente` o
`sin_medio`) — ajustar `busqueda_medios`/investigar SOLO esas tomas
puntuales, correr `narrator generate` de nuevo las veces que haga falta,
y subir a Drive al terminar (ver "Después de generar" abajo). No re-hagas
audio, logo, ni imágenes manuales — repetir eso es tokens gastados en algo
que ya estaba resuelto por código.

Los pasos de "Pipeline completo de un capítulo nuevo" de abajo son para
cuando alguien trabaja DIRECTO en una sesión interactiva sin pasar por el
bot (ej. esta misma sesión, ahora) — no repitas esos pasos si viniste de
una escalación del bot.

## Pipeline completo de un capítulo nuevo (guion.json sin audio)

Cuando llega un `guion.json` sin narración (ej. subido por Telegram o dejado en `C:\Android_in\<slug>\`), el audio se genera con `tts-kokoro` (proyecto hermano, `C:\tts-kokoro`) ANTES de tocar `illustrated-narrator`:

1. Copiar el `guion.json` a `C:\tts-kokoro\projects\<slug>\guion.json`.
2. Generar el audio: `C:\tts-kokoro\.venv\Scripts\python.exe -m tts_kokoro.cli --guion C:\tts-kokoro\projects\<slug>\guion.json --voz <voz> --velocidad 1.0` — la voz la indica el usuario (bot: `/voz`, default `am_adam`; si no se especifica en el mensaje, usar `am_adam`). Velocidad normal (1.0), no 1.15 — eso era una prueba anterior. Nunca asumir `pm_santa` fijo, eso era el default viejo. Esto deja un WAV por plano en `tts-kokoro/projects/<slug>/narracion/` y reescribe `duracion_seg`/`inicio_aprox` con la duración real.
3. Crear `C:\illustrated-narrator\projects\<slug>\`, copiar ahí el `guion.json` YA actualizado por tts-kokoro (no el original), y concatenar los WAV en orden (`p00.wav`, `p01.wav`, ...) a `narracion.wav` (48kHz estéreo PCM) con ffmpeg.
4. **Logo del canal**: si existe algún archivo `C:\illustrated-narrator\assets\dato_mata_gato_logo.*`, copiarlo a `projects/<slug>/media/p00/elegido_1.<ext>` (crear la carpeta si no existe) ANTES de correr `narrator generate` — el plano p00 (identidad_apertura/logo) SIEMPRE usa esta imagen en vez de buscar en Pexels/Wikimedia. Si no existe ningún logo todavía, seguir el comportamiento normal de búsqueda para p00.
5. A partir de acá sigue el flujo normal de "Refinamiento manual" de abajo: `NARR_NARRACION=voz poetry run narrator generate <slug> --vertical` (el `.env` compartido puede tener `NARR_NARRACION=mascota` de otro capítulo — SIEMPRE forzar `voz` con la variable de entorno para esta corrida, sin tocar el `.env`).
6. Revisar `media/manifest.json` en busca de fotos de país/lugar incoherente (patrón real ya visto: Pexels/Wikimedia devuelven resultados de cualquier país aunque la query diga "Mexico City" — hay que revisar caso por caso, no asumir que la query alcanza). Iterar: ajustar `busqueda_medios`, borrar el archivo resuelto en `images/<shot_id>.png` (y su copia en `images/clean/`) para forzar reintento, volver a correr `narrator generate`.
7. **Nunca hay foto real de la persona/caso** en Pexels/Wikimedia (son fuentes libres; las fotos de agencias de prensa como Cuartoscuro/Getty son de pago y NO se usan sin licencia verificable — no bajar ni copiar fotos de blogs/redes, republicar sin permiso no lo hace libre). Si el usuario pide "una foto para identificarlo", la alternativa es una ficha de identificación en TEXTO (nombre, alias, fechas, hechos públicos del propio guion) generada con Pillow y puesta como `media/<plano_id>/elegido_1.png` — no una fotografía de nadie.
8. **Verificar que el clip de cada plano sea de ESTA corrida**, no de una anterior: `ls -la clips/*.mp4` y comparar timestamps. Bug real ya visto: si un plano no encuentra medio nuevo, el pipeline puede reusar el `clip_listo` cacheado de `planos_alineados.json` con audio/timing de una voz/corrida vieja, sin loguear error — queda desincronizado si no se detecta a mano.

## Al refinar un capítulo

### Cuando pida "menos efectos"
Reducir/quitar en `guion.json`, por plano, dentro de `visual`:
- `overlay` (niebla|polvo|lluvia|burbujas|fuego) → quitar o `null`
- `shake` → `false`
- `motion` (calm|normal|energetic|impact) → bajar un nivel (ej. `energetic` → `normal`)

No tocar `narracion` ni el audio.

### Cuando pida mejorar coherencia de medios
- Ajustar `visual.busqueda_medios` (query explícita) y/o `visual.prompt_ia` para que la búsqueda real encuentre algo más pegado a la escena narrada.
- Revisar `projects/<slug>/media/manifest.json`: qué se eligió (`chosen`) y qué se descartó (`candidates`) por shot, con título/fuente/licencia. No guarda score numérico — se puede recalcular con `relevance_score(query, candidate.title)` (`domain/services/media_relevance.py`) para señalar planos con match débil.
- Señalar planos con relevancia baja para que el usuario decida: ajustar query, o subir una foto real a mano en `media/<plano_id>/elegido_N.*` (gana automáticamente sobre la búsqueda).

### Límite honesto que hay que respetar
No puedo ver ni oír el `.mp4` final. Nunca afirmar haber "validado" la coherencia audiovisual de un video viéndolo — el trabajo es sobre `guion.json`, `manifest.json` y los archivos de media. Lo que solo se puede juzgar viendo/escuchando el video se lo señalo al usuario para que lo revise él (celular).

### Antes de regenerar
- Mostrar el diff exacto de `guion.json` ANTES de correr `narrator generate`.
- Regenerar SOLO el capítulo indicado: `poetry run narrator generate <slug> --vertical`. Nunca el lote completo desde acá.

### Después de generar — SIEMPRE, sin preguntar
En cuanto `narrator generate` termina OK y existe `projects/<slug>/final.mp4`, si el capítulo vino de `C:\Android_in\<slug>\` (tiene guion.json/audio ahí):
1. Subir a Drive: `C:\dato-mata-gato-bot\.venv\Scripts\python.exe -m dato_mata_gato_bot.upload_cli <slug>`. Este comando ya arma el nombre `<titulo_del_guion>_<DDMMYYYY>.mp4` (calendario progresivo, arranca 25/08/2026, un día por capítulo nuevo — reintentos del mismo slug no le pisan la fecha) y actualiza `data/publish_schedule.json` solo — no armar el nombre ni tocar ese archivo a mano.
2. Crear `C:\Android_in\<slug>\_GENERADO.txt` (misma marca que usa `procesar_lote.ps1`) para que el lote no lo vuelva a procesar y pise este resultado.

Hacer esto automáticamente, sin pedir confirmación — preguntar acá en cada capítulo es ruido, no una decisión real que el usuario necesite tomar. Si hay dudas de contenido/medios pendientes de revisar, señalarlas igual, pero no bloquean este paso.

## Imágenes manuales enviadas por el usuario (Telegram u otro medio)

El bot de Telegram ya guarda las imágenes que el usuario manda ANTES de
`/generar` en `C:\Android_in\<slug>\imagenes_manuales\`, con nombre
`<plano_id>_<posicion>_<indice>.<ext>` (ej. `p01_inicio_1.jpg`) — ya
parseadas, no hay que interpretar texto/caption de Telegram.

Al arrancar el pipeline para un `slug` con esa carpeta no vacía: por cada
archivo, copiarlo a `projects/<slug>/media/<plano_id>/elegido_<indice>.<ext>`
(crear la carpeta si no existe) ANTES de correr `narrator generate`. El
pipeline YA prioriza automáticamente estos archivos sobre la búsqueda
(`_manual_override` en `research_plano_media.py`) — no hay que tocar
código para esto.

Si en cambio viene de otro medio (no el bot) y el usuario describe la
imagen con la convención en texto plano `p1 [inicio] [1]`, aplica lo
mismo: `p1` → normalizar a 2 dígitos (`p01`), `[inicio|medio|fin]` es
solo informativo, `[N]` es el índice de la toma.

**"Cortar si sobra, rellenar si falta" ya es el comportamiento existente — no construir nada nuevo:**
- Cuántas tomas tiene un plano lo decide `retention_plan.py` según `duracion_seg`, no el usuario. Si manda más imágenes que tomas tiene el plano, los índices de más simplemente no se usan — avisarle cuántas se usaron y cuántas sobraron.
- Si manda menos imágenes que tomas tiene el plano, los índices sin `elegido_*` se resuelven con la búsqueda real de siempre (Pexels/Wikimedia) — comportamiento ya existente.

Después de colocar la(s) imagen(es): borrar cualquier `images/<shot_id>.png` viejo que corresponda a esos índices si ya estaba resuelto de una corrida anterior (si no, el pipeline lo salta pensando que ya está listo), y volver a correr `narrator generate <slug> --vertical`.

## Rutas clave

| Ruta | Qué es |
|---|---|
| `projects/<slug>/guion.json` | Guion editable |
| `projects/<slug>/media/manifest.json` | Qué se investigó/eligió por shot |
| `projects/<slug>/planos_alineados.json` | Estado por plano — resumible, no hace falta borrar todo para reintentar un plano puntual |
| `projects/<slug>/final.mp4` | Salida del capítulo |
| `C:\dato-mata-gato-bot\data\publish_schedule.json` | Calendario de publicación (slug -> fecha/nombre/link de Drive) |
