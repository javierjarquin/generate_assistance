"""Guía la grabación del video demo para la auditoría de TikTok.

Va mostrando en pantalla, paso por paso, todo lo que el revisor tiene que
ver, y abre solo las páginas del sitio. Vos ponés a grabar y vas apretando
Enter.

NO automatiza el login ni el consentimiento de TikTok: esa pantalla la tenés
que operar vos. El demo existe justamente para probar que un creador real ve
los permisos y acepta -- automatizar ese clic invalidaría el demo, además de
arriesgar la cuenta.

    C:\\illustrated-narrator\\.venv\\Scripts\\python.exe tools/demo_auditoria.py <slug>
"""

import subprocess
import sys
import urllib.parse
import webbrowser
from pathlib import Path

from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent.parent
load_dotenv(RAIZ / ".env")

import os  # noqa: E402  -- después de load_dotenv

SITIO = "https://javierjarquin.github.io/dato-mata-gato-site"
PYTHON = str(RAIZ / ".venv" / "Scripts" / "python.exe")

_ANCHO = 74


def paso(numero: int, titulo: str, detalle: str = "") -> None:
    print("\n" + "=" * _ANCHO)
    print(f"  PASO {numero} — {titulo}")
    if detalle:
        print("=" * _ANCHO)
        for linea in detalle.strip().splitlines():
            print(f"  {linea.strip()}")
    print("=" * _ANCHO)
    input("\n  [Enter para continuar] ")


def _canjear_code(code: str) -> None:
    """Canjea el código por un access_token y lo deja listo para el paso 5.

    Va acá y no en tiktok_auth.py porque durante la grabación hay que revocar
    el acceso previo (si no, TikTok saltea la pantalla de permisos por estar
    ya autorizada), y eso invalida el token que hubiera en .env: el demo
    tiene que reponerlo en el momento o el paso siguiente falla.
    """
    import json
    import urllib.parse as _up

    import requests

    resp = requests.post(
        "https://open.tiktokapis.com/v2/oauth/token/",
        data={
            "client_key": os.getenv("NARR_TIKTOK_CLIENT_KEY"),
            "client_secret": os.getenv("NARR_TIKTOK_CLIENT_SECRET"),
            "code": _up.unquote(code),
            "grant_type": "authorization_code",
            "redirect_uri": os.getenv("NARR_TIKTOK_REDIRECT_URI"),
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    body = resp.json()
    if "access_token" not in body:
        print(f"\n  No se pudo canjear el código ({resp.status_code}): {body}")
        print("  Se sigue con el token que hubiera en .env.")
        return

    creds = RAIZ / "credentials"
    creds.mkdir(exist_ok=True)
    (creds / "tiktok_token.json").write_text(json.dumps(body, indent=2), encoding="utf-8")

    token = body["access_token"]
    env = RAIZ / ".env"
    texto = env.read_text(encoding="utf-8")
    linea = f"NARR_TIKTOK_ACCESS_TOKEN={token}"
    if "NARR_TIKTOK_ACCESS_TOKEN=" in texto:
        texto = "\n".join(
            linea if l.startswith("NARR_TIKTOK_ACCESS_TOKEN=") else l
            for l in texto.splitlines()
        )
    else:
        texto += f"\n{linea}\n"
    env.write_text(texto, encoding="utf-8")

    os.environ["NARR_TIKTOK_ACCESS_TOKEN"] = token
    print(f"\n  Token obtenido. Scopes: {body.get('scope')}")


def main() -> None:
    slug = sys.argv[1] if len(sys.argv) > 1 else "guion-campo-algodonero"

    print("\n" + "*" * _ANCHO)
    print("  DEMO PARA LA AUDITORÍA DE TIKTOK")
    print("*" * _ANCHO)
    print(
        "\n  ANTES DE GRABAR — revocá el acceso de la app en TikTok:\n"
        "    Perfil > Menú > Configuración y privacidad > Seguridad\n"
        "    > Aplicaciones conectadas (Manage app permissions)\n"
        "    y quitá 'datomatagato'.\n"
        "\n"
        "  Si no lo hacés, TikTok saltea la pantalla de permisos por estar\n"
        "  ya autorizada, y el revisor NO va a ver el consentimiento: es\n"
        "  motivo de rechazo.\n"
    )
    input("  [Enter cuando ya revocaste el acceso] ")

    print(
        "\n  Ahora poné a grabar la pantalla (Win+G, o OBS) y recién ahí\n"
        "  apretá Enter. Grabá todo de una sola pasada, sin cortes:\n"
        "  el revisor rechaza los demos con el flujo incompleto.\n"
    )
    input("  [Enter cuando ya estés grabando] ")

    paso(
        1,
        "El sitio de la app",
        "Se abre la web oficial declarada en el portal. El dominio que se ve "
        "acá tiene que coincidir con el Website URL de la app.",
    )
    webbrowser.open(f"{SITIO}/")

    paso(
        2,
        "Política de privacidad",
        "Mostrala unos segundos y bajá un poco, para que se vea que es "
        "accesible y que describe qué datos se usan y para qué.",
    )
    webbrowser.open(f"{SITIO}/privacidad.html")

    paso(3, "Términos de servicio", "Igual que la anterior: que se vea accesible.")
    webbrowser.open(f"{SITIO}/terminos.html")

    client_key = os.getenv("NARR_TIKTOK_CLIENT_KEY", "")
    redirect_uri = os.getenv("NARR_TIKTOK_REDIRECT_URI", "")
    params = {
        "client_key": client_key,
        "response_type": "code",
        "scope": "video.publish,user.info.basic",
        "redirect_uri": redirect_uri,
        "state": "illustrated-narrator-auth",
    }
    auth_url = "https://www.tiktok.com/v2/auth/authorize/?" + urllib.parse.urlencode(params)

    paso(
        4,
        "Autorización con TikTok (Login Kit)",
        """
        Se abre la pantalla de permisos de TikTok. ESTA PARTE LA HACÉS VOS:
          - Mostrá la pantalla COMPLETA, con los permisos que se piden
          - Que se vea el clic de aceptar
          - Después cae en el callback, en tu propio dominio, con el código
        Es el paso que más rechazos causa cuando se graba incompleto.
        """,
    )
    webbrowser.open(auth_url)

    print(
        "\n  Copiá el código que muestra la página de callback y pegalo acá.\n"
        "  (Se canjea por el token en el momento: así el demo muestra el\n"
        "  flujo completo de punta a punta, sin cortes.)\n"
    )
    code = input("  Código: ").strip()
    if code:
        _canjear_code(code)
    else:
        print("\n  Sin código: se sigue con el token que ya estaba en .env.")

    paso(
        5,
        "Pantalla de confirmación previa",
        f"""
        Ahora corre el publish para {slug}. Detenete en la pantalla de
        revisión y dejala visible unos segundos: ahí se ve que los datos
        salen de creator_info y que se respeta la config de la cuenta
        (opciones de privacidad, comentarios, dueto, stitch, duración).
        Cuando te pregunte, respondé 'y' para completar el flujo.
        """,
    )
    subprocess.run(
        [PYTHON, "-m", "illustrated_narrator.cli.main", "publish-tiktok", slug],
        cwd=str(RAIZ),
    )

    print("\n" + "*" * _ANCHO)
    print("  LISTO")
    print("*" * _ANCHO)
    print(
        "\n  Arriba tiene que verse la línea 'Publicado. publish_id: ...'.\n"
        "  ESA es la prueba de que la integración funciona: dejala unos\n"
        "  segundos en pantalla antes de cortar la grabación.\n"
        "\n  Después, revisá que el video:\n"
        "    - dure lo suficiente para leer cada pantalla\n"
        "    - pese menos de 50 MB\n"
        "    - esté en mp4 o mov\n"
        "    - muestre el flujo COMPLETO, sin cortes ni saltos\n"
    )
    # Sin esta pausa la ventana se cierra apenas termina el script y se
    # lleva el resultado: la grabación quedaba cortada justo antes de
    # 'Publicado. publish_id', que es lo único que el revisor necesita ver
    # como prueba (pasó en dos tomas reales).
    input("  [Enter recién cuando hayas cortado la grabación] ")


if __name__ == "__main__":
    main()
