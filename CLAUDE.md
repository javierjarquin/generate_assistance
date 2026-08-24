# CLAUDE.md

## Qué es este proyecto

`illustrated-narrator` genera videos narrados (verticales/horizontales) a partir de un `guion.json` (guion por planos) + un audio de narración real. Para las imágenes/video de cada plano investiga medios reales antes de considerar cualquier otra fuente: Pexels (fotos+video) y Wikimedia Commons primero, Openverse como respaldo; y como último recurso automático (`_proper_noun_fallback`, con nombres propios de la narración, para CUALQUIER plano) también prueba artículos de Wikipedia (imágenes de contenido embebidas) y NASA Images. Usa Whisper para transcribir/alinear la narración y ffmpeg para el ensamblado final.

## Config fija — no proponer cambiarla

- **Cero IA de imágenes fijas, sigue siendo el default.** Cada plano se resuelve con medio real investigado (`NARR_ENABLE_MEDIA_RESEARCH=1`). Nunca generar con Stable Diffusion/A1111 como "solución" a un plano sin match para una TOMA (imagen fija) — eso sigue prohibido.
- No propongas reactivar la generación de imagen-IA como atajo cuando una toma no encuentra medio real. El camino sigue siendo mejorar la búsqueda (ver más abajo) o dejar que el usuario lo revise/reemplace a mano.
- **Excepción única, ya decidida y acotada por el usuario**: si un PLANO ENTERO se queda sin ningún medio real (ninguna de sus tomas resolvió, tras agotar búsqueda + país + continente), y `NARR_VIDEO_FALLBACK_MAX_PLANOS` está activado (>0, default 0/desactivado), genera un clip corto con AnimateDiff (motion module estándar, ver `generate_plano_images.py`) SOLO para planos `imagen_ia`/`grafico_movimiento` — nunca `archivo_historico`, que afirma ser documental real. No amplíes este alcance (más planos, más duración, más tipos elegibles, imágenes fijas también) sin que el usuario lo pida explícitamente de nuevo — es una excepción angosta, no una reversión general de "cero IA".
- Si un plano se queda sin medio real Y sin este fallback (desactivado, o también falló), el capítulo se reporta como fallo — no se completa con un cartel de relleno silencioso.
- **Estado real del fallback de video-IA, confirmado con pruebas reales (23/08/2026, tras reiniciar Windows): SÍ es confiable, con el motion module ESTÁNDAR (no AnimateLCM).** Historial completo de la investigación: dos pruebas aisladas iniciales funcionaron con AnimateLCM, pero luego de varios reinicios de A1111 en la misma sesión de Windows todo empezó a fallar (memoria insuficiente / salida corrupta) -- eso resultó ser degradación del driver DirectML, se arregló con un reinicio de Windows. PERO reiniciar Windows reveló un segundo problema real, no relacionado con el driver: **AnimateLCM (8 pasos, CFG 1.5) colapsa en ruido/patrones repetidos para contenido de bajo detalle** (fondos casi sólidos, logos minimalistas -- ej. el prompt real de un plano `identidad_cierre`), aunque devuelva 200 OK (falla silenciosa, no un error). Confirmado en 3/3 pruebas con contenido minimalista, incluso reformulando el prompt de forma positiva. El motion module ESTÁNDAR (`mm_sd15_v2.safetensors`, sampler `Euler a`, CFG 7, 20 pasos -- ver `animatediff_a1111_adapter.py`) SÍ dio salida coherente en 5/5 pruebas, tanto para contenido rico como minimalista, y se confirmó con una corrida real end-to-end completa (`narrator generate` de punta a punta, plano sin medio real -> video-IA -> clip renderizado -> video final con subtítulos y marca aplicados correctamente encima). Es ~2x más lento que AnimateLCM (~9-10 min por clip de 2s vs ~4 min), pero esa es la configuración correcta: los planos que más necesitan este fallback (donde la búsqueda real ya agotó todo) tienden a ser justo el tipo de contenido minimalista/conceptual donde AnimateLCM fallaba. Sigue desactivado por default (`NARR_VIDEO_FALLBACK_MAX_PLANOS=0`) -- activarlo es una decisión explícita del usuario, no algo que Claude proponga solo.
- **403 de `upload.wikimedia.org` en descargas de figuras públicas -- causa real confirmada, mitigado pero NO eliminado.** `upload.wikimedia.org` (la CDN de descarga, no la API de búsqueda) devuelve 403 en conexiones REUTILIZADAS de una misma `requests.Session` (keep-alive) bajo carga -- no por cookies ni volumen total (confirmado con pruebas aisladas: la misma Session con `Connection: close` en cada descarga resolvió 3/3 casos que fallaban repetidamente). Fix aplicado a los tres adapters que descargan de ese host (`wikimedia_adapter.py`, `openverse_adapter.py`, `wikipedia_article_adapter.py`): limpiar cookies + `Connection: close` por descarga, y `403` agregado a `status_forcelist` de los reintentos. **Aun así, una corrida real completa (23/08/2026) siguió mostrando 403 intermitentes en ~25 descargas distintas durante ~20 minutos** -- el bloqueo no es 100% determinístico por URL, es más bien una degradación de tasa de éxito bajo carga sostenida contra ese host (tres adapters distintos, cada uno con su propio throttle, comparten el mismo host sin coordinación entre sí). Lo que SÍ salvó el resultado: cada plano puede tener varias tomas que derivan la MISMA query (`derive_query` es a nivel de plano, no de toma -- ver `research_plano_media.py`), así que varias tomas hermanas reintentan independientemente los mismos candidatos; en la práctica alguna de esas repeticiones termina teniendo éxito. Confirmado en esa misma corrida: las fotos reales de Isabel Miranda de Wallace y de Hugo Alberto Wallace Miranda SÍ llegaron al video final pese al 403 repetido en ambos archivos en intentos anteriores. **No "arreglar" esta redundancia agregando una caché de "URL ya falló, no reintentar" a nivel de adapter -- se probó y se revirtió: reduce las descargas desperdiciadas pero también reduce las chances de que una toma hermana posterior tenga éxito donde una anterior falló, que es justo el mecanismo que hoy rescata las fotos de figuras públicas.** Si en el futuro se quiere reducir el 403 de raíz, la siguiente hipótesis no probada es un rate-limiter compartido entre los tres adapters (no por adapter) contra ese host específico -- requiere ir despacio y volver a validar con una corrida real completa, no con pruebas aisladas (el síntoma solo aparece bajo carga real sostenida).
- **`_proper_noun_fallback` no distribuía entre varias figuras del mismo plano -- arreglado (23/08/2026).** Bug real: un plano mencionaba a Isabel Miranda de Wallace Y a Felipe Calderón, pero el fallback probaba los nombres siempre en el mismo orden y se quedaba con el primero que tuviera candidatos disponibles -- como Wikimedia devolvía más de un candidato con "Isabel Miranda" en el título, las tomas que necesitaban el fallback se resolvían ahí y "Felipe Calderón" (correctamente extraído) nunca se intentaba. Fix: cada plano trackea qué nombres ya usó una toma hermana (`used_names` en `execute()`) y los prioriza al final de la lista en la siguiente toma.
- **Empate en `relevance_score` se resolvía por orden de inserción, no por especificidad -- arreglado (23/08/2026).** `relevance_score` es una fracción (0..1) de palabras de la query presentes en el título -- con una query de 2 palabras (nombre propio), CUALQUIER título que las mencione da 1.0, sin importar cuántas palabras más tenga alrededor. Bug real: para "Felipe Calderón", un título de una foto de protesta ("Brigadas Querétaro - Protesta contra reforma energética de Felipe Calderón - CDMX 2008.jpg") empataba en 1.0 con un retrato limpio ("Felipe Calderón.jpg") -- y como `sorted()` es estable, ganaba el que Wikimedia devolvía primero, no el mejor match. Fix: `title_specificity()` (`media_relevance.py`) cuenta las palabras del título y se usa como desempate en los 3 sitios que rankean candidatos (`_best_match`, `_proper_noun_fallback`, `_geo_fallback`) -- título más corto/limpio gana el empate, título largo que solo MENCIONA el nombre de paso pierde.
- **Modo mascota (Balam) desactivado por default (23/08/2026), a pedido explícito del usuario.** `NARR_NARRACION` en `.env` volvió a `voz` (el default del código ya era ese; `.env` lo pisaba a `mascota` desde un traspaso anterior). No reactivarlo por default sin que el usuario lo pida de nuevo -- un guion puntual la puede seguir pidiendo vía `meta.mascota.modo="mascota"`.
- **Cartel de cierre fijo (`/cierre` en el bot, 23/08/2026) -- reduce las escaladas automáticas a Claude.** El plano `identidad_cierre` (logo del canal sobre negro puro, última sección de CUALQUIER guion) es contenido genérico que ninguna búsqueda de stock real puede encontrar -- confirmado en dos escalamientos reales del pipeline del bot a una sesión de Claude (`guion-cassez-vallarta`, `guion-cisne-negro-completo`) con la MISMA descripción de plano en ambos casos. `dato-mata-gato-bot/pipeline.py::_apply_cierre()` copia un archivo fijo (subido una vez por Telegram con `/cierre`, guardado en `C:\illustrated-narrator\assets\dato_mata_gato_cierre.*`) al plano cuya `seccion=="identidad_cierre"` como `elegido.<ext>` -- mismo mecanismo que ya existía para el logo de apertura en p00 (`_apply_logo`), pero localizando el plano por `seccion` en vez de un id fijo porque el id del cierre varía (`p09`/`p10`/`p11`... según cuántos planos tenga el guion). Verificado con una corrida real (`guion-wallace-fulltest`): el plano de cierre queda resuelto sin ninguna llamada a Pexels/Wikimedia. Si el usuario todavía no subió un cierre con `/cierre`, el comportamiento es el de siempre (busca real, puede quedar sin medio).
- **Reutilizar la mejor foto real ya encontrada en vez de dejar tomas sin medio (23/08/2026) -- otra causa recurrente de escalada.** Un plano con más tomas que fotos realmente DISTINTAS disponibles (query genérica con solo 1-2 candidatos buenos pero el plano tiene 4-5 tomas) dejaba las tomas sobrantes `sin_medio` (confirmado en `guion-cassez-vallarta`: 14 tomas sin medio en 6 planos con descripciones genéricas que sí deberían encontrar algo). `execute()` en `research_plano_media.py` trackea `best_reusable` (el último candidato real elegido por una toma hermana del mismo plano); si una toma agota búsqueda + nombre propio + país/continente sin encontrar NADA propio, reutiliza esa foto en vez de quedar vacía -- nunca pisa un match legítimo, aunque sea débil, solo cubre el caso de cero matches.
- **A1111 daba 500 en la SEGUNDA generación de video-IA de una misma corrida -- arreglado (23/08/2026).** Confirmado en corrida real (`guion-caro-quintero`): la primera generación de video-IA salió bien, la segunda (~15 min después, mismo proceso de A1111 sin reiniciar entre medio) dio `500 Internal Server Error` en `/sdapi/v1/txt2img` -- agotamiento de VRAM entre generaciones consecutivas de AnimateDiff. Fix: `a1111_lifecycle.py` mata el proceso que escucha en el puerto de A1111 (por puerto vía `Get-NetTCPConnection`, no por texto de línea de comando -- evita el bug de autoeliminación ya documentado más abajo) y lo relanza, esperando a que vuelva a responder; `AnimateDiffA1111Adapter.generate()` lo llama antes de CADA generación solo si `NARR_A1111_RESTART_BEFORE_USE=1` (nunca por default, solo el bot lo activa en sus corridas automáticas). **De paso se encontró y arregló un bug real y separado en `tools/run_a1111.bat`**: `call webui-user.bat` (nombre pelado) fallaba con "no se reconoce como un comando" en este sistema -- cmd.exe no busca el directorio actual para `call` de un nombre sin prefijo acá, aunque `cd` ya estuviera en el lugar correcto y el archivo existiera (confirmado con `dir`). `call .\webui-user.bat` (prefijo explícito) sí funciona -- ya corregido en el `.bat` (versionado). Esto probablemente explica por qué `_kick_off_a1111_if_needed()` en `dato-mata-gato-bot/pipeline.py` nunca arrancaba A1111 de verdad -- las generaciones de video-IA que sí funcionaron antes dependían de que alguien lo hubiera arrancado a mano. **Gotcha adicional, NO versionado (fuera de git, específico de esta instalación local)**: el propio `tools\stable-diffusion-webui-directml\webui-user.bat` tenía saltos de línea Unix (LF) en vez de CRLF -- si se reinstala/re-clona esa carpeta alguna vez, puede volver a aparecer un síntoma parecido ("no se reconoce como un comando") y hay que convertirlo a CRLF de nuevo (`sed 's/$/\r/'` o equivalente).
- **`MAX_AUTO_RETRIES` en `dato-mata-gato-bot/pipeline.py` subido de 2 a 10 (23/08/2026), a pedido explícito del usuario** -- con 2, el pipeline automático escalaba a Claude en casi todos los capítulos. La mayoría de los reintentos son rápidos (solo re-investigan las tomas marcadas -- `resolve_shot_asset` se salta lo ya resuelto), así que no vuelve mucho más lento el caso típico.
- **`GOOGLE_DRIVE_FOLDER_ID` siempre vacío por orden de import -- la subida a Drive fallaba SIEMPRE, era una 4ta causa real de escalada a Claude (23/08/2026).** `dato-mata-gato-bot/bot.py` importaba `pipeline` (que leía `GOOGLE_DRIVE_FOLDER_ID` como constante de MÓDULO) antes de llamar `load_dotenv()` -- quedaba fijo en `""` para siempre, sin importar qué tuviera el `.env`. Confirmado en una corrida real: el video se generó bien pero la subida falló con "Falta GOOGLE_DRIVE_FOLDER_ID en el .env del bot" pese a que el `.env` sí lo tiene. Fix: `pipeline.py::_upload_to_drive()` lee la variable en el momento (dentro de la función, no como constante de módulo), y `bot.py` mueve `load_dotenv()` ANTES de sus imports de `dato_mata_gato_bot.*` (previene la misma clase de bug para cualquier variable futura). **Segunda causa separada, misma síntoma**: `upload_cli.py` (la herramienta que la propia instrucción de escalada le dice a Claude que use para subir a mano) nunca llamaba `load_dotenv()` en absoluto -- arreglado igual. Si en el futuro aparece "Falta X en el .env" pese a que el `.env` sí lo tiene, sospechar primero de esto: buscar `= os.getenv(...)` a nivel de módulo (no adentro de una función) en cualquier archivo de `dato-mata-gato-bot`, y confirmar que `load_dotenv()` corre antes de que ese módulo se importe.

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
- Logo del canal copiado a `media/p00/elegido.*` (si existe)
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
4. **Logo del canal**: si existe algún archivo `C:\illustrated-narrator\assets\dato_mata_gato_logo.*`, copiarlo a `projects/<slug>/media/p00/elegido.<ext>` (crear la carpeta si no existe) ANTES de correr `narrator generate` — el plano p00 (identidad_apertura/logo) SIEMPRE usa esta imagen en vez de buscar en Pexels/Wikimedia. Importante: `elegido.<ext>` SIN índice, no `elegido_1.<ext>` — p00 dura ~4s estimados pero la duración real a veces pasa el umbral de 4.0s y se parte en 2 tomas; `elegido_1` solo cubre la primera y la segunda cae en la búsqueda real (confirmado en corridas reales: eligió una foto de una moneda de bitcoin). `elegido.*` sin índice cubre todas las tomas del plano, sin importar en cuántas se termine partiendo. Si no existe ningún logo todavía, seguir el comportamiento normal de búsqueda para p00.
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

#### `pais_incoherente` (país/lugar equivocado en el resultado)
Antes de agregar el sitio a `_SENSITIVE_BLOCKLIST` en `media_relevance.py` (parche reactivo, uno por uno cada vez que aparece un caso nuevo — Auschwitz, Alcatraz, etc.), revisar si el `guion.json` ya declara `meta.pais` (ej. `"pais": "México"`). Si NO lo tiene, agregarlo — `ResearchPlanoMedia` ya lo usa como fallback automático (ensancha la query con el país, y si tampoco alcanza, con el continente vía `continente_de()`) para CUALQUIER plano sin medio real, y de paso reduce la tasa de estos falsos positivos en primer lugar (una query ya acotada a "Mexico" difícilmente devuelve Alcatraz como mejor resultado). `visual.pais` por plano pisa el default del guion si una escena puntual pasa en otro país. Seguir agregando al blocklist solo para el caso puntual ya detectado, no como sustituto de declarar el país.

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
| `tools\stable-diffusion-webui-directml\` | A1111 local (DirectML, AMD) — necesario para el fallback de video-IA (ver nota de confiabilidad arriba, "Config fija"). Extensión `sd-webui-animatediff` + modelos `mm_sd15_v2.safetensors`/`mm_sd15_AnimateLCM.safetensors` + LoRA `AnimateLCM_sd15_t2v_lora.safetensors` ya instalados (no reinstalar). Arrancar con `tools\run_a1111.bat` antes de una corrida que use `NARR_VIDEO_FALLBACK_MAX_PLANOS>0` — no se autolanza. Si quedó un proceso `python.exe launch.py` corriendo de una corrida anterior sin cerrar bien, mata ese proceso ANTES de arrancar de nuevo -- confirmado en una corrida real que un huérfano así se queda con ~6GB de VRAM y causa fallos de memoria en la siguiente corrida que parecen (pero no son) el mismo bug de memoria insuficiente de la tarjeta. |
