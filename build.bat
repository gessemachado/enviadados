@echo off
echo === Build SyncAgent.exe ===

pip install fdb requests pyinstaller --quiet

pyinstaller --onefile --name SyncAgent --distpath dist ^
    --add-data "config.ini;." ^
    src/main.py

echo.
echo === Build concluido ===
echo Copie dist\SyncAgent.exe e config.ini para o servidor
pause
