@echo off
scp -P 22022 "C:\aplicativos\enviadados\produtos.html" root@108.174.148.133:/var/www/enviadados/
scp -P 22022 "C:\aplicativos\enviadados\clientes.html" root@108.174.148.133:/var/www/enviadados/
echo Concluido!
pause
