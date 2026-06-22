@echo off
chcp 65001 >nul 2>&1
title Examen Digital - Servidor

echo ==============================================
echo   EXAMEN DIGITAL - INICIANDO SERVIDOR
echo ==============================================
echo.

REM Obtener la ruta del script y proyecto
set SCRIPT_DIR=%~dp0
set PROJECT_ROOT=%SCRIPT_DIR%..
cd /d "%PROJECT_ROOT%"

REM Verificar que Python esta instalado
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python no esta instalado.
    echo.
    echo Por favor instala Python 3.10 o superior desde:
    echo   https://www.python.org/downloads/
    echo.
    echo Asegurate de marcar "Add Python to PATH" durante la instalacion.
    echo.
    pause
    exit /b 1
)

echo [OK] Python encontrado
python --version
echo.

REM Crear entorno virtual si no existe
if not exist "venv" (
    echo [INFO] Creando entorno virtual...
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] No se pudo crear el entorno virtual.
        pause
        exit /b 1
    )
    echo [OK] Entorno virtual creado
) else (
    echo [OK] Entorno virtual ya existe
)
echo.

REM Activar entorno virtual e instalar dependencias
echo [INFO] Instalando dependencias...
call venv\Scripts\activate.bat

REM Instalar dependencias si es necesario
pip install -q -r requirements.txt
if errorlevel 1 (
    echo [ERROR] No se pudieron instalar las dependencias.
    echo.
    pause
    exit /b 1
)
echo [OK] Dependencias instaladas
echo.

REM Obtener la direccion IP local
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /i "IPv4" ^| findstr /v "127.0.0.1"') do (
    set LOCAL_IP=%%a
    set LOCAL_IP=!LOCAL_IP:~1!
    goto :found_ip
)
:found_ip

if not defined LOCAL_IP set LOCAL_IP=localhost

REM Mostrar informacion de acceso
echo ==============================================
echo.
echo   SERVIDOR INICIADO EXITOSAMENTE
echo.
echo   Acceso local:  http://localhost:8000
if not "%LOCAL_IP%"=="localhost" (
    echo   Acceso red:    http://%LOCAL_IP%:8000
)
echo.
echo   Presiona Ctrl+C para detener el servidor
echo.
echo ==============================================
echo.

REM Iniciar el servidor
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
