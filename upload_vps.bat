@echo off
echo Enviando arquivos para VPS...
echo (sera solicitada a senha root 4 vezes)
echo.

scp -P 22022 "C:\aplicativos\enviadados\mobile\home.html" root@108.174.148.133:/var/www/enviadados/mobile/
scp -P 22022 "C:\aplicativos\enviadados\mobile\financeiro.html" root@108.174.148.133:/var/www/enviadados/mobile/
scp -P 22022 "C:\aplicativos\enviadados\mobile\produtos.html" root@108.174.148.133:/var/www/enviadados/mobile/
scp -P 22022 "C:\aplicativos\enviadados\mobile\sw.js" root@108.174.148.133:/var/www/enviadados/mobile/

echo.
echo Concluido!
pause
