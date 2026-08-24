"""Reinicia el proceso de A1111 antes de cada generación de video-IA --
opt-in, NUNCA se dispara solo (ver AnimateDiffA1111Adapter).

Motivo real: en una corrida real (guion-caro-quintero, 23/08/2026) la
PRIMERA generación de video-IA de la corrida salió bien, pero la SEGUNDA
(~15 min después, mismo proceso de A1111 sin reiniciar entre medio) dio
500 Internal Server Error en /sdapi/v1/txt2img -- pinta a agotamiento de
VRAM entre generaciones consecutivas de AnimateDiff, no un error de red
pasajero (mismo síntoma de fondo, aunque distinta causa puntual, que la
degradación de driver DirectML ya documentada en CLAUDE.md, que también
se resolvía reiniciando). Reiniciar el proceso antes de CADA uso da un
estado de VRAM limpio siempre, en vez de tener que distinguir "primer uso
de la corrida" de "uso siguiente".
"""

import logging
import subprocess
import time
from urllib.parse import urlsplit

import requests

logger = logging.getLogger(__name__)

_KILL_TIMEOUT = 15
_READY_POLL_INTERVAL = 3.0
# launch.py arranca varios procesos python.exe relacionados (no solo el que
# termina escuchando el puerto) -- confirmado en una corrida real: matar
# solo el PID del puerto dejaba hasta 6 procesos "launch.py" huérfanos
# acumulados tras varios reinicios, cada uno reteniendo VRAM, lo que
# terminaba causando el mismo síntoma (500 "not enough GPU memory") que se
# intentaba arreglar. Hay que matarlos TODOS.
#
# El string de búsqueda se arma partido (concatenado) adentro del script de
# PowerShell, no como literal en el comando que Python invoca -- si el
# comando que lanza ESTE proceso (visible para WMI) contiene el string
# completo, el filtro se automatchea a sí mismo y se mata solo (bug real ya
# confirmado en esta misma investigación: exit code 255 por autoeliminación
# al filtrar por 'launch.py' o 'stable-diffusion-webui' directo).
_FIND_ALL_PIDS_SCRIPT = (
    "$needle = 'launch' + '.py'; "
    "Get-CimInstance Win32_Process | "
    "Where-Object { $_.CommandLine -match $needle } | "
    "Select-Object -ExpandProperty ProcessId"
)
_KILL_ALL_SCRIPT = (
    "$needle = 'launch' + '.py'; "
    "Get-CimInstance Win32_Process | "
    "Where-Object { $_.CommandLine -match $needle } | "
    "Select-Object -ExpandProperty ProcessId | "
    "ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }"
)


def _find_a1111_pids() -> list[int]:
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", _FIND_ALL_PIDS_SCRIPT],
            capture_output=True, text=True, timeout=10,
        )
        return [int(line) for line in result.stdout.splitlines() if line.strip().isdigit()]
    except (subprocess.SubprocessError, OSError):
        return []


def _kill_all_a1111_processes() -> None:
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", _KILL_ALL_SCRIPT],
            capture_output=True, timeout=_KILL_TIMEOUT,
        )
    except (subprocess.SubprocessError, OSError):
        pass


def restart_a1111(base_url: str, bat_path: str, cwd: str, ready_timeout: float = 180.0) -> bool:
    """Mata TODOS los procesos de A1111 (launch.py y lo que haya spawneado,
    no solo el que escucha el puerto -- ver _FIND_ALL_PIDS_SCRIPT) y lo
    relanza, esperando hasta ready_timeout segundos a que vuelva a
    responder. True si quedó listo, False si no -- el llamador decide si
    abortar el fallback o intentar igual (nunca lanza, un reinicio fallido
    no debe tirar abajo toda la corrida)."""
    pids = _find_a1111_pids()
    if pids:
        logger.info("Reiniciando A1111 (pids %s) antes de generar video-IA", pids)
        _kill_all_a1111_processes()
        time.sleep(3)  # deja liberar el puerto/VRAM antes de relanzar
    else:
        logger.info("A1111 no estaba corriendo -- arrancándolo antes de generar video-IA")

    try:
        subprocess.Popen(
            [bat_path], cwd=cwd,
            creationflags=subprocess.CREATE_NO_WINDOW,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    except OSError as exc:
        logger.warning("No se pudo relanzar A1111 (%s)", exc)
        return False

    deadline = time.monotonic() + ready_timeout
    while time.monotonic() < deadline:
        try:
            resp = requests.get(f"{base_url}/sdapi/v1/sd-models", timeout=5)
            if resp.ok:
                logger.info("A1111 listo tras reinicio")
                return True
        except requests.RequestException:
            pass
        time.sleep(_READY_POLL_INTERVAL)
    logger.warning("A1111 no respondió tras %.0fs de reiniciarlo", ready_timeout)
    return False
