@echo off
REM setup.bat — instala dependencias y configura el entorno
REM Ejecutar una sola vez desde cmd o doble-click

echo ============================================================
echo  TCL 65C6K Price Tracker — Setup
echo ============================================================
echo.

cd /d "%~dp0"

REM Crear entorno virtual
echo [1/4] Creando entorno virtual...
python -m venv .venv
call .venv\Scripts\activate.bat

REM Instalar dependencias
echo [2/4] Instalando dependencias...
pip install --upgrade pip -q
pip install -r requirements.txt -q

REM Instalar Playwright con Chromium
echo [3/4] Instalando Playwright Chromium...
playwright install chromium

REM Copiar .env si no existe
echo [4/4] Configurando .env...
if not exist .env (
    copy .env.example .env
    echo   .env creado — EDITA este archivo con tus credenciales antes de continuar.
) else (
    echo   .env ya existe — OK.
)

echo.
echo ============================================================
echo  Setup completo!
echo.
echo  Proximos pasos:
echo  1. Edita .env con tus credenciales (email, Telegram, WhatsApp)
echo  2. Ejecuta: python main.py   (para probar manualmente)
echo  3. Ejecuta: powershell -ExecutionPolicy Bypass -File setup_scheduler.ps1
echo     (para programar la tarea diaria a las 23:00)
echo ============================================================
pause
