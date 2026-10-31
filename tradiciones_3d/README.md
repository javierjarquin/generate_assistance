# tradiciones_3d

Render del nicho **"el porqué de las tradiciones"** de Dato Mata Gato (30/10/2026): video vertical 3D hecho
solo con código (Remotion + three.js, primitivas, sin modelos ni IA). Sale del POC del cempasúchil
(`C:\clip_assistance\analisis\nicho_tradiciones\poc_cempasuchil`), ya genérico: el guion declara qué se ve
en cada escena y `src/Video.tsx` lo dibuja.

## Cómo se usa

El bot lo corre solo cuando el guion trae `"formato": "tradiciones"` (`pipeline.run_tradiciones`):

    C:\illustrated-narrator\.venv\Scripts\python.exe tradiciones_3d\scripts\render.py <slug> [--hoja]

1. Voz Fish 3 por escena (VoiceStudio en `:3900`, voz `cbbc2aa7`, `num_step` 32), en
   `C:\Android_in\<slug>\voz_3d\`. Una escena cuyo texto no cambió no se vuelve a pedir.
2. Whisper `small` da los tiempos por palabra; las palabras salen del guion (difflib).
3. `remotion render` → `out/<slug>.mp4`. Con `--hoja`, `out/<slug>_hoja.jpg` (un cuadro por segundo).

El bot mueve el video al proyecto del narrador, le pega la portada gancho (`poc_remotion/scripts/portada.py`)
y lo archiva en `C:\Android_in\lotes\<lote>\`.

Para ver el ejemplo en el Studio: `npm run studio` (abre `ejemplos/cempasuchil.props.json`, sin audio).

## El guion

Cada escena: `texto`, `visual` (objetos con sus props), `camara`, `etiquetas` y `claves`. Un prop numérico
se anima dentro de la escena con `{"de": 0, "a": 1, "desde": 0.55, "hasta": 0.85}` (y `"regresa": [a, b]`
para volver). Ejemplo completo: `ejemplos/cempasuchil.guion.json`.

**El catálogo vive en dos lados**: los objetos en `src/Objetos.tsx` y su lista de props en el bot
(`instruccion_tradiciones.CATALOGO`), que es lo que Claude ve y lo que la revisión acepta. Un objeto o prop
nuevo va en los dos; si solo va aquí, Claude no lo conoce, y si solo va allá, el render lo ignora.

## Biblioteca de modelos (estilo juguete)

`public/modelos/` trae 111 modelos low-poly de [Kenney](https://kenney.nl) (CC0: se usan y redistribuyen sin
permiso), con `indice.json` (`"food/corn": "elote"`). Los arma `scripts/biblioteca.py`: baja los paquetes,
copia los de `ELEGIDOS` y escribe el índice. Para agregar uno, súmalo a `ELEGIDOS` y vuelve a correrlo. El bot
lee ese índice directo: la lista de modelos vive en un solo lugar.

En el guion: `{"objeto": "Modelo", "modelo": "food/corn", "alto": 0.4}`. Se escala a `alto` y se apoya en
`y = 0` (con `Piso`, `posicion` en `y = -1.6`).

**El protagonista tiene que existir** (candado del 30/10/2026): un `Modelo` o un objeto hecho por código
(`Flor`, `PapelPicado`, `Velas`, `Ofrenda`). La calaverita de la primera corrida, armada con esferas sueltas,
se veía como figuras geométricas; por eso `Forma` queda para detalles (máximo 2 por escena) y la IA gratis solo
propone temas con protagonista disponible.

## Pendiente

- Lo muy mexicano no existe gratis en ninguna biblioteca (calaverita de azúcar, pan de muerto, piñata, rosca,
  copal): se hace por código en `Objetos.tsx`, uno por tema de temporada, y se suma a `PROTAGONISTAS` del bot.
- Bloom real (`@react-three/postprocessing`) y transiciones entre escenas.
