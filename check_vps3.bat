@echo off
echo Config enviadados:
ssh -p 22022 root@108.174.148.133 "cat /etc/nginx/sites-enabled/enviadados"
pause
echo Config simulador:
ssh -p 22022 root@108.174.148.133 "cat /etc/nginx/sites-enabled/simulador"
pause
