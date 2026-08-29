# Auditoría de la Content Posting API de TikTok

Guía para dejar la publicación automática en TikTok igual que la de Facebook.
Mientras la app no esté auditada, **todo lo que se publique por API queda
privado de forma permanente** (`SELF_ONLY`) y no se puede volver público
retroactivamente. Por eso la auditoría no es opcional.

> **No se automatiza TikTok con navegador headless.** Automatizar la subida
> web para saltear la auditoría viola sus términos, la detección de
> automatización en el flujo de subida es agresiva, y la sanción típica es
> baneo de la cuenta. El canal completo vale mucho más que el trámite.

## Estado actual

| Pieza | Estado |
|---|---|
| Sitio con políticas y callback | ✅ https://javierjarquin.github.io/dato-mata-gato-site/ |
| `TikTokPublisher` (init + chunking + upload) | ✅ construido y con tests |
| `query_creator_info()` | ✅ construido y con tests |
| Pantalla de confirmación previa | ✅ `narrator publish-tiktok` |
| Flujo OAuth | ✅ `tools/tiktok_auth.py` |
| App registrada en el portal | ⬜ **lo hace el titular** |
| Credenciales en `.env` | ⬜ **lo hace el titular** |
| Auditoría aprobada | ⬜ pendiente de envío |
| TikTok enganchado al job diario | ⬜ después de la aprobación |

## Paso 1 — Registrar la app

En [developers.tiktok.com](https://developers.tiktok.com) → *Manage apps* →
*Connect an app*. Crear antes una **organización**.

**Datos a cargar** (copiar tal cual):

| Campo | Valor |
|---|---|
| App icon | `C:\illustrated-narrator\assets\dato_mata_gato_logo.*` (redimensionar a 1024×1024) |
| App name | `Dato Mata Gato Publisher` |
| Category | News / Entertainment |
| Platform | **Web** |
| Website URL | `https://javierjarquin.github.io/dato-mata-gato-site/` |
| Terms of Service URL | `https://javierjarquin.github.io/dato-mata-gato-site/terminos.html` |
| Privacy Policy URL | `https://javierjarquin.github.io/dato-mata-gato-site/privacidad.html` |
| Redirect URI | `https://javierjarquin.github.io/dato-mata-gato-site/auth/` |

**Descripción sugerida** (describe lo que la herramienta realmente hace, que
es lo que se audita):

> Herramienta interna de un solo titular que publica en la cuenta propia del
> canal Dato Mata Gato los capítulos ya producidos. No ofrece servicio a
> terceros ni administra cuentas ajenas. Antes de cada publicación muestra
> una pantalla de confirmación construida con `creator_info`, que respeta las
> opciones de privacidad e interacción configuradas por el creador.

**Productos y scopes**: agregar *Content Posting API*, activar **Direct
Post**, y pedir `video.publish` + `user.info.basic`.

## Paso 2 — Verificar la propiedad de la URL

Obligatorio para el Content Posting API. TikTok da un archivo de texto con
una firma (método *URL prefix*). Agregarlo a la raíz del repo del sitio:

```bash
cd C:\dato-mata-gato-site
# copiar ahí el archivo que descargó el portal, por ejemplo:
git add tiktok-developers-site-verification.txt
git commit -m "Verificacion de propiedad para TikTok"
git push
```

Esperar ~1 minuto a que Pages recompile y confirmar en el portal.

## Paso 3 — Credenciales

El portal da `client_key` y `client_secret`. Escribirlos **directamente** en
`C:\illustrated-narrator\.env` (nunca pegarlos en un chat ni commitearlos —
`credentials/` y `.env` están en `.gitignore`):

```
NARR_TIKTOK_CLIENT_KEY=...
NARR_TIKTOK_CLIENT_SECRET=...
NARR_TIKTOK_REDIRECT_URI=https://javierjarquin.github.io/dato-mata-gato-site/auth/
```

El `redirect_uri` debe coincidir **carácter por carácter** con el registrado.

## Paso 4 — Autorizar la cuenta

```bash
cd C:\illustrated-narrator
poetry run python tools/tiktok_auth.py
```

Imprime una URL: abrirla, aceptar con la cuenta del canal, y el callback
muestra el `code`. Pegarlo en la consola. Guarda el token en
`credentials/tiktok_token.json`.

Desde acá ya se puede publicar, pero **en privado** hasta la auditoría:

```bash
poetry run narrator publish-tiktok <slug>
```

## Paso 5 — Grabar el video demo

Es lo que más rechazos genera. Hay que mostrar el flujo **completo y sin
cortes**, en una sola grabación de pantalla:

1. Ejecutar `poetry run python tools/tiktok_auth.py` y mostrar la **pantalla
   de autorización de TikTok completa**, incluyendo los permisos que se piden
   y el clic de aceptación. No saltear esta parte.
2. Mostrar el callback devolviendo el código y el token guardándose.
3. Ejecutar `poetry run narrator publish-tiktok <slug>` y detenerse en la
   **pantalla de confirmación**, que muestra:
   - cuenta (nickname y username, traídos de `creator_info`)
   - duración del video contra `max_video_post_duration_sec`
   - caption exacto que se va a publicar
   - nivel de privacidad elegido **y las opciones disponibles de la cuenta**
   - estado de comentarios / dueto / stitch según la configuración real
4. Confirmar y mostrar la publicación completándose.
5. Mostrar las páginas de [privacidad](https://javierjarquin.github.io/dato-mata-gato-site/privacidad.html)
   y [términos](https://javierjarquin.github.io/dato-mata-gato-site/terminos.html)
   abiertas y accesibles.

Máximo 50 MB por video, hasta 5 videos.

### Causas frecuentes de rechazo

- Demo sin el flujo de autorización completo.
- Ofrecer opciones que el creador tiene deshabilitadas → por eso la pantalla
  se arma desde `creator_info` y `permite_privacidad()` bloquea un nivel no
  permitido antes de subir nada.
- No mostrar pantalla de revisión antes de publicar.
- Políticas inaccesibles.
- Pedir scopes que no se usan → se piden solo `video.publish` y
  `user.info.basic`.

## Paso 6 — Después de la aprobación

1. Cambiar en `.env`: `NARR_TIKTOK_PRIVACY_LEVEL=PUBLIC_TO_EVERYONE`
2. Enganchar TikTok al job diario de las 20:00, junto a Facebook
   (`daily_publish.py` en `dato-mata-gato-bot`).

## Tiempos

- Acceso al producto: días.
- Auditoría de contenido: **semanas**.

Mientras tanto Facebook publica solo y TikTok se sube a mano con el material
que el bot manda por Telegram todos los días.
