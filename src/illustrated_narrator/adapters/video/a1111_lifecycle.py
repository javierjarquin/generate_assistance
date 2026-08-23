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

_KILL_TIMEOUT = 10
_READY_POLL_INTERVAL = 3.0


def _find_listening_pid(port: int) -> int | None:
    """PID que escucha en el puerto -- más confiable que matchear la línea
    de comando (un filtro con 'launch.py'/'stable-diffusion-webui' en el
    string puede automatchearse a sí mismo si corre desde PowerShell, visto
    antes en esta misma investigación: exit code 255 por autoeliminación)."""
    try:
        result = subprocess.run(
            [
                "powershell", "-NoProfile", "-Command",
                f"(Get-NetTCPConnection -LocalPort {port} -State Listen "
                f"-ErrorAction SilentlyContinue).OwningProcess",
            ],
            capture_output=True, text=True, timeout=10,
        )
        pid_str = result.stdout.strip()
        return int(pid_str) if pid_str.isdigit() else None
    except (subprocess.SubprocessError, ValueError, OSError):
        return None


def _kill_pid(pid: int) -> None:
    try:
        subprocess.run(
            [
                "powershell", "-NoProfile", "-Command",
                f"Stop-Process -Id {pid} -Force -ErrorAction SilentlyContinue",
            ],
            capture_output=True, timeout=_KILL_TIMEOUT,
        )
    except (subprocess.SubprocessError, OSError):
        pass


def restart_a1111(base_url: str, bat_path: str, cwd: str, ready_timeout: float = 180.0) -> bool:
    """Mata el proceso actual de A1111 (si hay uno escuchando en el puerto
    de base_url) y lo relanza, esperando hasta ready_timeout segundos a que
    vuelva a responder. True si quedó listo, False si no -- el llamador
    decide si abortar el fallback o intentar igual (nunca lanza, un
    reinicio fallido no debe tirar abajo toda la corrida)."""
    port = urlsplit(base_url).port or 7860

    pid = _find_listening_pid(port)
    if pid is not None:
        logger.info("Reiniciando A1111 (pid %d) antes de generar video-IA", pid)
        _kill_pid(pid)
        time.sleep(2)  # deja liberar el puerto/VRAM antes de relanzar
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
