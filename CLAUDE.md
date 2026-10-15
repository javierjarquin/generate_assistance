# CLAUDE.md

Actualizado el 15/10/2026 contra el código. El detalle histórico de cada regla (bugs, pruebas, fechas) está en `docs/historial_decisiones.md`: ábrelo solo si una regla de aquí no te alcanza.

## Qué es este proyecto

`illustrated-narrator` arma videos narrados (verticales) del canal **Dato Mata Gato** a partir de un `guion.json` por planos + la narración: alinea la voz con Whisper, resuelve la imagen de cada toma y ensambla con ffmpeg. Casi siempre lo maneja el bot (`C:\dato-mata-gato-bot`, `pipeline.py`), no una persona.

## Cómo es el pipeline hoy (lo que manda sobre cualquier texto viejo)

- **Voz**: `tts-kokoro` con motor **VoiceStudio** (`TTS_ENGINE=voicestudio`, contenedor Docker `voicestudio`, puerto 3900). Los guiones `guion-*` (true crime y fórmula de cercanía) van con **Fish 3** (`VOICESTUDIO_VOICE_ID_CRIMEN`, num_step 32, gancho con guidance/velocidad propios); trivia y mitos con la voz de Javier. La voz clonada nueva de Javier está **desactivada** desde el 14/10. El `--voz am_adam` que aún se pasa es de Kokoro y no aplica a VoiceStudio.
- **Evidencia real, sin IA, en los `guion-*`** (desde 29/09): el guion trae `evidencia` (prensa, documento, lugar, ficha) y `dato_mata_gato_bot/evidencia.py` la baja y la deja en `C:\Android_in\<slug>\imagenes_manuales\` antes de `narrator generate`. No se buscan fotos genéricas para esos planos.
- **Render final con Remotion** (`poc_remotion/`, `RENDER_VIDEO=remotion`): `scripts/render_plus.py` arma CapituloPlus (contador del gancho, mapa del lugar, contradicción, fichas que resaltan lo que dice la voz, palabras en rojo, notas animadas, fotos de las notas y archivo de Pexels con crédito) y `scripts/portada.py` la portada (estilo A, "la nota"), que se pega como primer cuadro. El `final.mp4` de ffmpeg queda de respaldo como `final_ffmpeg.mp4` y se usa si Remotion falla.
- **Stock genérico apagado** desde el 20/09: `NARR_PEXELS_API_KEY` está vacía a propósito (traía fotos que no eran del caso). `DMG_ARCHIVO_PEXELS_KEY` es solo para las tomas de archivo marcadas como tales en Remotion.
- **Lotes**: la fábrica (`dato_mata_gato_bot/fabrica.py`, `/lotegrande N dia`) escribe y genera sola y **archiva en `C:\Android_in\lotes\<lote>\` sin subir a Drive ni publicar**. Javier publica a mano.

## Reglas fijas — no proponer cambiarlas

- **Cero IA en imágenes fijas.** Si una toma no encuentra medio real, se mejora la búsqueda o lo revisa el usuario; nunca se genera con Stable Diffusion/A1111.
- **Única excepción, acotada**: video-IA corto con AnimateDiff (motion module estándar `mm_sd15_v2`, no AnimateLCM) solo para planos ENTEROS sin medio real de tipo `imagen_ia`/`grafico_movimiento`, nunca `archivo_historico`. Lo activa `NARR_VIDEO_FALLBACK_MAX_PLANOS` (hoy `2` en el `.env`). No ampliar su alcance sin que el usuario lo pida. A1111 no se autolanza: `tools\run_a1111.bat` (mata antes cualquier `launch.py` huérfano, se queda con ~6 GB de VRAM).
- Un plano sin medio real y sin ese respaldo es **fallo del capítulo**, no un cartel de relleno.
- **Token de Drive caducado** (`invalid_grant`): no lo arregles; dile al usuario que corra `C:\dato-mata-gato-bot\.venv\Scripts\python.exe -m dato_mata_gato_bot.drive_auth`. Los videos no se pierden.
- **403 de `upload.wikimedia.org`**: es intermitente bajo carga y lo rescatan las tomas hermanas que reintentan la misma query. No agregues caché de "URL fallida".
- **Modo mascota apagado** por default (`NARR_NARRACION=voz`); un guion puntual lo pide con `meta.mascota.modo="mascota"`.
- **Tono**: los hechos se cuentan directo, sin la vieja "regla del morbo". Tres excepciones: (a) de un suicidio, todo menos el método; (b) nunca describir fotos filtradas de una víctima (Ley Ingrid); (c) nunca IA de víctimas reales identificables ni recreaciones.
- **Sin plano de apertura**: p00 es el primer plano de contenido (el gancho); el logo solo va en `identidad_cierre` (`_apply_cierre` del bot).
- No puedo ver ni oír el `.mp4`: no afirmar que "validé" lo audiovisual; lo que solo se juzga viendo, se le señala al usuario.

## Si esta sesión la abrió el bot (`claude -p`)

- Solo para generar o ajustar videos con las herramientas de este workspace; no conversación general.
- Cada mensaje es un proceso `claude -p` nuevo y corto. **Nunca corras `tts_kokoro.cli`, `narrator generate` ni otro paso largo en segundo plano**: si el proceso termina antes, el resultado queda huérfano. Todo en primer plano, aunque tarde.
- El bot no te usa para recolectar archivos: guion e imágenes ya están en disco.

### Cuando el bot te escala un capítulo ("El pipeline automático...")

Ya se hizo sin ti: audio, proyecto armado, evidencia/imágenes manuales copiadas (no las revises ni las reemplaces) y varias corridas de `narrator generate` con reintentos (`MAX_AUTO_RETRIES` = 10). **Haz solo lo que el mensaje marca como pendiente** (tomas `pais_incoherente` o `sin_medio`): ajusta `busqueda_medios` de esas tomas, vuelve a correr `narrator generate` y, si el capítulo es de `/generar` (no de un lote), súbelo como dice "Después de generar".

## Capítulo nuevo a mano (sesión interactiva, sin el bot)

1. Copiar `guion.json` a `C:\tts-kokoro\projects\<slug>\` y generar el audio con `C:\tts-kokoro\.venv\Scripts\python.exe -m tts_kokoro.cli --guion <ruta> --voz am_adam --velocidad 1.0` (con VoiceStudio la voz real la toma del `.env`).
2. Crear `projects/<slug>/`, copiar el `guion.json` YA actualizado por tts-kokoro y concatenar los WAV en orden a `narracion.wav` (48 kHz estéreo).
3. `NARR_NARRACION=voz poetry run narrator generate <slug> --vertical` (forzar `voz` sin tocar el `.env`).
4. Revisar `media/manifest.json` por país/lugar incoherente. Si falla, primero declarar `meta.pais` en el guion (el fallback ensancha con país y continente); `_SENSITIVE_BLOCKLIST` solo para el caso puntual.
5. **No hay foto real de personas** en fuentes libres: sin agencias de pago ni fotos de blogs/redes. La alternativa es una ficha en texto hecha con Pillow.
6. Verificar que cada clip sea de esta corrida (`ls -la clips/*.mp4`): un `clip_listo` cacheado de una corrida vieja queda desincronizado sin error.

## Al refinar un capítulo

- **"Menos efectos"**: en `visual` de cada plano, quitar `overlay`, `shake: false`, bajar `motion` un nivel (calm|normal|energetic|impact). No tocar narración ni audio.
- **Coherencia de medios**: ajustar `visual.busqueda_medios`; el manifest dice qué se eligió y qué se descartó (sin score: recalcular con `relevance_score` de `media_relevance.py`). Un archivo en `media/<plano>/elegido_N.*` gana siempre.
- Antes de regenerar: mostrar el diff exacto de `guion.json` y regenerar solo ese capítulo.

## Después de generar (solo capítulos de `/generar`, no lotes ni fábrica)

Sin preguntar: subir con `C:\dato-mata-gato-bot\.venv\Scripts\python.exe -m dato_mata_gato_bot.upload_cli <slug>` (arma el nombre y el calendario solo) y crear `C:\Android_in\<slug>\_GENERADO.txt`.

## Imágenes manuales

Las que manda el usuario quedan en `C:\Android_in\<slug>\imagenes_manuales\<plano>_<pos>_<n>.<ext>` y van a `projects/<slug>/media/<plano>/elegido_<n>.<ext>` (`_manual_override` las prioriza). Cuántas tomas tiene un plano lo decide `retention_plan.py`: las de más no se usan y las que faltan se buscan. Al reemplazar, borrar el `images/<shot>.png` viejo para forzar el reintento.

## Rutas clave

| Ruta | Qué es |
|---|---|
| `projects/<slug>/guion.json` · `media/manifest.json` · `planos_alineados.json` | Guion, medios elegidos y estado por plano (resumible) |
| `projects/<slug>/final.mp4` (`final_ffmpeg.mp4`, `portada_nota.jpg`) | Salida (respaldo de ffmpeg y portada) |
| `poc_remotion/` | Render con Remotion: `scripts/render_plus.py`, `scripts/multimedia.py`, `scripts/portada.py`, `plus_datos/reglas_medios.json` |
| `C:\dato-mata-gato-bot\src\dato_mata_gato_bot\` | Bot: `pipeline.py`, `fabrica.py`, `evidencia.py`, `instruccion_cercania.py`, `herramientas_guion.py` |
| `C:\Android_in\fabrica\<lote>\estado.json` · `C:\Android_in\lotes\<lote>\` | Estado de la fábrica y videos archivados |
| `docs/historial_decisiones.md` | Detalle histórico de las reglas de arriba |
