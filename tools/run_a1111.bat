@echo off
rem Arranca AUTOMATIC1111 con API. Detecta la variante instalada:
rem - stable-diffusion-webui          (NVIDIA/CUDA, laptop)
rem - stable-diffusion-webui-directml (AMD, PC de casa)
cd /d "%~dp0"
if exist "stable-diffusion-webui\webui-user.bat" (
    cd stable-diffusion-webui
) else if exist "stable-diffusion-webui-directml\webui-user.bat" (
    cd stable-diffusion-webui-directml
) else (
    echo No se encontro ninguna instalacion de A1111 en tools\
    exit /b 1
)
call webui-user.bat
