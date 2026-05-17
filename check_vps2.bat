@echo off
echo Verificando configuracao nginx...
ssh -p 22022 root@108.174.148.133 "echo === Config enviadados === && cat /etc/nginx/sites-enabled/enviadados && echo === Config simulador === && cat /etc/nginx/sites-enabled/simulador && echo === Erro nginx === && tail -5 /var/log/nginx/error.log"
pause
