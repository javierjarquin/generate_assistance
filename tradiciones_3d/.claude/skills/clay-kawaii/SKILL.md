---
name: clay-kawaii
description: Estilo "plastilina kawaii pastel" del canal papasia (papás primerizos). Úsala al crear o retocar cualquier objeto, escena, letrero o decorado del render 3D de papasia (tradiciones_3d/src/Clay.tsx), o cuando pidan que algo se vea "más cute".
---

# Plastilina kawaii pastel (canal papasia)

El look que pidió Javier el 15/11/2026, con una imagen de referencia: un
malvavisco con carita sentado en una nube rosa, fondo pastel desenfocado, una
estrella y un arcoíris. Todo lo de papasia se dibuja así.

## Dónde vive

- `tradiciones_3d/src/Clay.tsx`: materiales, piezas (`Bola`, `Caja`, `Rollo`,
  `torno`), la carita, `Bebe`, `Cuna`, `Biberon`, la nube (`Cojin`), el decorado
  de atrás y las versiones de plastilina de `Calendario`, `Sol`, `Particulas` y
  `Forma`.
- `tradiciones_3d/src/Video.tsx`: el ambiente `cuarto` (`claro: true`) enciende
  el estilo: luz de estudio, decorado en un lienzo aparte desenfocado, subtítulos
  y letreros claros. `scripts/render.py` pone `cuarto` a todo guion con
  `formato: "papasia"`.
- El motor es Remotion + three.js (React Three Fiber), **no Blender**: un video
  de 60 s sale en ~1 minuto. Con Blender/Cycles serían horas por video y la
  fábrica no alcanzaría. Las reglas de abajo son las del prompt original de
  Blender, traducidas a este motor.

## Las cinco reglas

1. **Geometría gordita, sin esquinas.** Solo esferas, cápsulas (`Rollo`), sólidos
   de torno (`torno`, con perfil suavizado) y cajas redondeadas (`Caja`). Nada de
   `boxGeometry` ni cilindros con canto vivo. Las formas extruidas (estrella,
   corazón, fichas) llevan bisel grande.
2. **Material de plastilina.** Siempre `<Arcilla color=… />`: mate (roughness
   ~0.8), un poco de luz propia que hace de "subsurface", `sheen` suave y un
   relieve de ruido muy sutil (`bumpMap`). No usar `meshStandardMaterial` suelto.
   Lo pintado encima (ojos, boca, chapitas) va con `Tinta`, liso y sin sombra.
3. **Solo pasteles.** La paleta está en `PASTEL`. Cualquier color que venga del
   guion pasa por `pastel(color)`: mismo tono, menos saturación, mucha luz. Nunca
   negro, café oscuro ni colores saturados.
4. **Luz de estudio difusa y efecto miniatura.** `Luces`: cielo y suelo claros,
   una principal casi cenital con sombra blanda y un contraluz rosa. Sin
   tone mapping (`flat`). La profundidad de campo se imita: el decorado va en un
   segundo lienzo con `filter: blur()`. Lo que está en primer plano va nítido.
   Las intensidades de three son físicas (÷π): con menos de ~1.5 de luz de cielo
   todo sale gris; con más de ~2 se lava.
5. **Partes separadas con el origen en la articulación.** Cada parte es su
   `<group>` con el pivote donde se dobla (cuello, hombro, base del cuerpo), para
   animar con squash & stretch: respira, rebota, se ladea, se mece. Nada rígido.

## La carita (`Carita`)

Mínima, como la referencia: ojos de punto muy separados y bajos, con un brillito;
boca chiquita; chapitas rosas siempre. Estados: dormido (medias lunas),
inquieto (cejitas y boca hacia abajo), llanto (ojos `> <`, lágrimas, boca
abierta). Nada de caras realistas, pestañas largas ni dientes.

## Reglas del canal que el estilo no puede romper

- Es salud infantil: la **cuna va vacía** (sin almohadas, cobijas ni juguetes) y
  el bebé no sale boca abajo.
- Los props de `Bebe`, `Cuna` y `Biberon` son los del `CATALOGO` de
  `C:\dato-mata-gato-bot\src\dato_mata_gato_bot\instruccion_papasia.py`. Un prop
  u objeto nuevo va en los dos lados, o la revisión del guion lo rechaza.
- El cuadro es vertical: a la distancia normal solo se ve de x ≈ -1 a x ≈ 1.
- Dato Mata Gato y tradiciones no usan este estilo: no tocar `Objetos.tsx` ni los
  otros ambientes para lograr algo de papasia.

## Cómo agregar un objeto

1. Dibujarlo en `Clay.tsx` con las piezas de arriba. Altura ~2 unidades, base en
   y ≈ -1.0 (ahí queda la nube). Si brilla, `Destellos`.
2. Registrarlo en `OBJETOS` de `Video.tsx` (con `t: true` si se anima solo) y en
   el `CATALOGO` del bot.
3. Verlo antes de renderizar un video:

   ```
   set ANDROID_IN=C:\Android_in\papasia
   C:\illustrated-narrator\.venv\Scripts\python.exe scripts\cuadros.py prueba guion-papasia-gases-bebe
   ```

   Deja un cuadro por escena y una hoja en `out\cuadros\`. Mirar la hoja: que no
   se vea plano (tiene que haber sombra propia), que nada salga gris ni lavado y
   que la figura no tape los subtítulos (arriba) ni el letrero (abajo).
4. `npx tsc --noEmit -p .` y un render completo con `scripts\render.py <slug>`.

## El prompt original (referencia, es para Blender)

> Escena en estilo 3D Clay Kawaii / Soft Clay Pastel para un video educativo
> sobre bebés. 1) Geometría: primitivas básicas (cubos redondeados con Bevel y
> Subdivision Surface, esferas y cápsulas), formas gorditas, suaves y sin
> esquinas duras (malvavisco o plastilina moldeada). 2) Materiales: Principled
> BSDF mate suave (Roughness 0.75–0.85), ligero Subsurface Scattering (0.15) y
> Noise Texture muy sutil al Bump, textura artesanal de plastilina. 3) Paleta:
> solo pasteles suaves (crema, rosa pastel, azul bebé, amarillo mantequilla).
> 4) Iluminación y cámara: estudio muy difuso (Area Lights grandes y suaves) y
> Depth of Field para efecto miniatura. 5) Animación: objetos por partes con el
> origen en las articulaciones, para rebotes suaves (squash and stretch).
