"""Localiza el binario de ffmpeg: config, PATH, o instalación de winget (Gyan.FFmpeg).

Portado de shorts-factory (misma máquina, mismo build de ffmpeg ya validado).
"""

import logging
import os
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)


def resolve_ffmpeg(configured: str = "ffmpeg") -> str:
    if configured != "ffmpeg" and Path(configured).exists():
        return configured
    found = shutil.which(configured)
    if found:
        return found
    packages = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages"
    if packages.exists():
        for candidate in sorted(packages.glob("Gyan.FFmpeg*/**/bin/ffmpeg.exe")):
            logger.info("ffmpeg encontrado vía winget: %s", candidate)
            return str(candidate)
    logger.warning("ffmpeg no encontrado; se usará '%s' y fallará si no está en PATH", configured)
    return configured
