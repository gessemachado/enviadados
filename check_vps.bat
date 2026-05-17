@echo off
echo Verificando VPS...
ssh -p 22022 root@108.174.148.133 "echo === Arquivos mobile === && ls /var/www/enviadados/mobile/ 2>/dev/null || echo PASTA NAO ENCONTRADA && echo === Sites enabled === && ls /etc/nginx/sites-enabled/ && echo === Nginx status === && systemctl is-active nginx"
pause
