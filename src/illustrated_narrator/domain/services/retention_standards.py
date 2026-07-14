"""Estándares de retención de la herramienta — la referencia única de "qué hace
que un video corto conserve al espectador", con los valores que el pipeline
aplica y de dónde salen.

Investigado (2026, datos públicos de retención de Shorts/Reels/TikTok). Fuentes
en el README. Los otros módulos importan estas constantes para no dispersar los
números mágicos.

RESUMEN DE LAS REGLAS
---------------------
1. Los primeros 0-3s deciden todo: 50-60% del abandono ocurre ahí. El gancho
   (título + promesa visual + movimiento inmediato) debe entrar en <2.5s.
   -> ass_writer: título con POP inmediato; motion_profile: punch-in por toma.

2. Cambio visual cada 2-4s. Una imagen fija más tiempo se siente estática.
   -> retention_plan: parte los planos largos en varias tomas (MAX_SHOT_SECONDS).

3. Sin dissolves en los primeros 5s (los cortes secos "despiertan" al scroller).
   -> ffmpeg_assembler: transiciones casi-secas dentro de la ventana inicial.

4. Subtítulos de 2-3 palabras, alto contraste, fuente gruesa, sin caja.
   Palabra hablada resaltada (optimización con sonido apagado).
   -> ass_writer: chunks con pop de escala + karaoke amarillo, Arial Black.

5. El movimiento debe seguir al contenido (impacto = rápido/violento; calma =
   lento). Movimiento uniforme = sensación de sopor.
   -> motion_profile: perfiles calm/normal/energetic/impact.

6. Audio a -14 LUFS (estándar de las plataformas); un video callado se pierde.
   -> ffmpeg_assembler: loudnorm en el ensamblado.

7. Estructura: Gancho (0-3s) -> Escalada -> Payoff (último 15-25%) -> CTA/loop.
   -> generate_narration_video: título de gancho + tarjeta de cierre (CTA).
"""

# Ventana crítica del gancho: el título/promesa debe estar resuelto aquí.
HOOK_WINDOW_SECONDS = 2.5

# Los primeros N segundos van con cortes secos (sin dissolve).
NO_DISSOLVE_WINDOW_SECONDS = 5.0

# Cambio visual: ninguna toma debería superar esto (ver retention_plan).
MAX_SHOT_SECONDS = 4.0

# Subtítulos: palabras por golpe de texto.
CAPTION_MAX_WORDS = 3

# Objetivo de sonoridad integrada (LUFS) — estándar YouTube/Shorts/TikTok.
TARGET_LUFS = -14.0

# Duración recomendada del corte para mantener ritmo (referencia, no obligatorio).
IDEAL_CUT_SECONDS = (2.0, 4.0)
