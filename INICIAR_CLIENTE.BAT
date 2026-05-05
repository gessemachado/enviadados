@echo off
title Obsidian — SyncAgent
color 0A
echo.
echo  ==========================================
echo   Obsidian Analytics — SyncAgent
echo  ==========================================
echo.

if not exist "%~dp0SyncAgent.exe" (
    echo [ERRO] SyncAgent.exe nao encontrado na pasta %~dp0
    echo Contate o suporte.
    pause
    exit /b
)

if not exist "%~dp0config.ini" (
    echo [ERRO] config.ini nao encontrado na pasta %~dp0
    echo Contate o suporte.
    pause
    exit /b
)

cd /d "%~dp0"

echo  Iniciando sincronizacao...
echo  Pressione Ctrl+C para parar
echo.

SyncAgent.exe

echo.
echo  SyncAgent encerrado.
pause
