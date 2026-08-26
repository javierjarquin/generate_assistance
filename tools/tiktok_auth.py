"""Autorización OAuth de TikTok (Content Posting API) -- semi-manual.

A diferencia de Google Drive (drive_auth.py en dato-mata-gato-bot), TikTok
EXIGE que redirect_uri sea HTTPS y esté pre-registrado en el portal de
desarrolladores -- no admite http://localhost, así que no se puede levantar
un servidor local automático como hace el flujo de Google. Por eso el
código de autorización se pega a mano una sola vez.

Antes de correr esto:
1. Creá una app en https://developers.tiktok.com/ (Manage apps), agregale
   el producto "Content Posting API", pedile el scope `video.publish`.
2. Registrale una Redirect URI HTTPS cualquiera que controles (puede ser
   una página que no exista de verdad -- el navegador va a mostrar un
   error 404 después de loguearte, ESO ES NORMAL, lo que importa es el
   parámetro ?code=... en la URL de esa página de error).
3. Completá en .env: NARR_TIKTOK_CLIENT_KEY, NARR_TIKTOK_CLIENT_SECRET,
   NARR_TIKTOK_REDIRECT_URI (la misma URL exacta registrada en el paso 2).

Uso:
    python tools/tiktok_auth.py             # autorización nueva
    python tools/tiktok_auth.py --refresh    # renovar con el refresh_token guardado

El access_token dura 24hs; el refresh_token dura 365 días. Este script NO
actualiza .env solo -- imprime los valores para que los pegues vos mismo
(NARR_TIKTOK_ACCESS_TOKEN), y guarda el refresh_token en
credentials/tiktok_token.json para poder renovar con --refresh sin repetir
el login por navegador.
"""

import json
import os
import sys
import urllib.parse
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

_TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
_AUTH_URL = "https://www.tiktok.com/v2/auth/authorize/"
_SCOPE = "video.publish"

CREDENTIALS_DIR = Path(__file__).resolve().parent.parent / "credentials"
TOKEN_PATH = CREDENTIALS_DIR / "tiktok_token.json"


def _env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        print(f"Falta {name} en .env -- completalo antes de correr esto.")
        raise SystemExit(1)
    return value


def _print_tokens(body: dict) -> None:
    print("\n=== Listo ===")
    print(f"access_token (pegalo en .env como NARR_TIKTOK_ACCESS_TOKEN):\n{body['access_token']}")
    print(f"\nVence en {body.get('expires_in', '?')}s (~24hs). refresh_token guardado en {TOKEN_PATH}")
    print("Cuando el access_token venza, corré: python tools/tiktok_auth.py --refresh")


def authorize_interactive() -> None:
    client_key = _env("NARR_TIKTOK_CLIENT_KEY")
    client_secret = _env("NARR_TIKTOK_CLIENT_SECRET")
    redirect_uri = _env("NARR_TIKTOK_REDIRECT_URI")

    params = {
        "client_key": client_key,
        "response_type": "code",
        "scope": _SCOPE,
        "redirect_uri": redirect_uri,
        "state": "illustrated-narrator-auth",
    }
    auth_url = f"{_AUTH_URL}?{urllib.parse.urlencode(params)}"
    print("1. Abrí esta URL en el navegador y logueate con la cuenta de TikTok del canal:\n")
    print(auth_url)
    print(
        "\n2. Después de aceptar los permisos, el navegador te va a redirigir a tu "
        "redirect_uri (probablemente muestre un error 404 -- es esperable, no hay "
        "servidor de verdad ahí). Copiá el valor del parámetro 'code' de esa URL."
    )
    code = input("\n3. Pegá acá el código (solo el valor de code=...): ").strip()
    code = urllib.parse.unquote(code)

    resp = requests.post(
        _TOKEN_URL,
        data={
            "client_key": client_key,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    body = resp.json()
    if resp.status_code != 200 or "access_token" not in body:
        print(f"Falló el intercambio de código ({resp.status_code}): {body}")
        raise SystemExit(1)

    CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)
    TOKEN_PATH.write_text(json.dumps(body, indent=2), encoding="utf-8")
    _print_tokens(body)


def refresh() -> None:
    if not TOKEN_PATH.exists():
        print(f"No hay {TOKEN_PATH} -- corré la autorización sin --refresh primero.")
        raise SystemExit(1)
    saved = json.loads(TOKEN_PATH.read_text(encoding="utf-8"))
    client_key = _env("NARR_TIKTOK_CLIENT_KEY")
    client_secret = _env("NARR_TIKTOK_CLIENT_SECRET")

    resp = requests.post(
        _TOKEN_URL,
        data={
            "client_key": client_key,
            "client_secret": client_secret,
            "grant_type": "refresh_token",
            "refresh_token": saved["refresh_token"],
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    body = resp.json()
    if resp.status_code != 200 or "access_token" not in body:
        print(f"Falló el refresh ({resp.status_code}): {body}")
        raise SystemExit(1)

    TOKEN_PATH.write_text(json.dumps(body, indent=2), encoding="utf-8")
    _print_tokens(body)


if __name__ == "__main__":
    if "--refresh" in sys.argv:
        refresh()
    else:
        authorize_interactive()
