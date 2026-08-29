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


def main() -> None:
    slug = sys.argv[1] if len(sys.argv) > 1 else "guion-campo-algodonero"

    print("\n" + "*" * _ANCHO)
    print("  DEMO PARA LA AUDITORÍA DE TIKTOK")
    print("*" * _ANCHO)
    print(
        "\n  Poné a grabar la pantalla AHORA (Win+G, o OBS) y recién ahí\n"
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
    print("  LISTO — podés cortar la grabación")
    print("*" * _ANCHO)
    print(
        "\n  Antes de subirlo, revisá que el video:\n"
        "    - dure lo suficiente para leer cada pantalla\n"
        "    - pese menos de 50 MB (recortá o bajá la calidad si no)\n"
        "    - esté en mp4 o mov\n"
        "    - muestre el flujo COMPLETO, sin cortes ni saltos\n"
    )


if __name__ == "__main__":
    main()
