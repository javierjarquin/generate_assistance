# Mascota Balam - carpeta de sprites (Capitulo1)

Esta carpeta la lee el modo mascota del narrador. Cada subcarpeta es una ACCION;
dentro va su animacion como PNGs numerados (00.png, 01.png, ...) con FONDO
TRANSPARENTE. El prompt exacto de cada una esta en su `PROMPT.txt`.

## Obligatorias vs opcionales
- OBLIGATORIAS: `talk` (boca en movimiento) y `idle` (boca cerrada). Sin estas
  dos el modo mascota no arranca.
- OPCIONALES: wave, walk, point, jump, celebrate, scared, surprised, think, sad,
  laugh. Cuantas mas pongas, mas rica la actuacion. Si falta una, el motor cae
  a otra parecida (no se rompe).

## Como se dispara cada expresion (segun el guion de Capitulo1)
- wave      -> entrada (plano 1, saluda) + la mascota entra caminando
- walk      -> cruza la pantalla de extremo a extremo en cada plano
- surprised -> "De repente...", "lo increible" (p02, p04)
- point     -> datos/cifras: "veinte kilometros", "doscientos kilometros" (p03, p06, p08)
- think     -> "Imaginalo" (p05)
- scared    -> "una sola explosion", "veneno" (p07, p09)
- celebrate -> tarjeta de cierre (CTA), si la activas

## Reglas de arte (importante)
- Fondo 100% transparente (PNG alfa). Nada de blanco.
- Mismo lienzo (1024x1024) y misma escala/encuadre en TODAS.
- Cuerpo entero, centrado, pies abajo. `walk` en perfil/3-4. `jump` con pies en el aire.
- `talk` boca ABIERTA (2 frames), `idle` boca CERRADA.
- Consistencia: ancla todas a la imagen de referencia (mismo personaje/colores).

## Cuantos frames
- talk: 2 (00 abierta, 01 media)   - idle: 2 (parpadeo)   - walk: 2 (zancada A/B)
- el resto: 1 basta (2+ si quieres animarlas)

## Para renderizar con mascota
Desde la raiz del repo:

    NARR_NARRACION=mascota NARR_MASCOTA_PATH=./projects/Capitulo1/mascota poetry run narrator generate Capitulo1

(requiere haber grabado projects/Capitulo1/narracion.wav con el guion nuevo)

Config opcional: NARR_MASCOTA_POS, NARR_MASCOTA_HEIGHT_FRAC, NARR_MASCOTA_FPS,
NARR_MASCOTA_VOICE_THRESHOLD.
