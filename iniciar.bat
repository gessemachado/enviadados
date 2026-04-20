@echo off
title SyncAgent — Firebird ^> Supabase
color 0A
echo.
echo  ==========================================
echo   SyncAgent — Firebird para Supabase
echo  ==========================================
echo.

REM Verifica se Python esta instalado
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERRO] Python nao encontrado. Instale Python 32-bit em python.org
    pause
    exit /b
)

REM Mostra arquitetura do Python
for /f "tokens=*" %%i in ('python -c "import struct; print(struct.calcsize(chr(80))*8)"') do set BITS=%%i
echo  Python detectado: %BITS% bits

REM Instala dependencias se necessario
echo.
echo  Verificando dependencias...
pip show fdb >nul 2>&1
if errorlevel 1 (
    echo  Instalando fdb...
    pip install fdb --quiet
)
pip show requests >nul 2>&1
if errorlevel 1 (
    echo  Instalando requests...
    pip install requests --quiet
)
echo  Dependencias OK.
echo.

REM Verifica se config.ini existe
if not exist "%~dp0config.ini" (
    echo [ERRO] config.ini nao encontrado na pasta %~dp0
    pause
    exit /b
)

REM Vai para a pasta do script
cd /d "%~dp0"

echo  ==========================================
echo   Iniciando sincronizacao...
echo   Pressione Ctrl+C para parar
echo  ==========================================
echo.

python "%~dp0syncagent.py"

echo.
echo  SyncAgent encerrado.
pause
