@echo off
title Dashboard — Obsidian
echo Iniciando dashboard...
cd /d "%~dp0"
start "" http://localhost:8080/calendario_vendas.html
python -m http.server 8080
