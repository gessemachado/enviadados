@echo off
echo Enviando arquivos desktop...
scp -P 22022 "C:\aplicativos\enviadados\financeiro.html" root@108.174.148.133:/var/www/enviadados/
scp -P 22022 "C:\aplicativos\enviadados\relatorio_estoque.html" root@108.174.148.133:/var/www/enviadados/
scp -P 22022 "C:\aplicativos\enviadados\perfil.html" root@108.174.148.133:/var/www/enviadados/
scp -P 22022 "C:\aplicativos\enviadados\produtos.html" root@108.174.148.133:/var/www/enviadados/
scp -P 22022 "C:\aplicativos\enviadados\calendario_vendas.html" root@108.174.148.133:/var/www/enviadados/

echo Enviando arquivos mobile...
scp -P 22022 "C:\aplicativos\enviadados\mobile\home.html" root@108.174.148.133:/var/www/enviadados/mobile/
scp -P 22022 "C:\aplicativos\enviadados\mobile\financeiro.html" root@108.174.148.133:/var/www/enviadados/mobile/
scp -P 22022 "C:\aplicativos\enviadados\mobile\perfil.html" root@108.174.148.133:/var/www/enviadados/mobile/
scp -P 22022 "C:\aplicativos\enviadados\mobile\projecao.html" root@108.174.148.133:/var/www/enviadados/mobile/
scp -P 22022 "C:\aplicativos\enviadados\mobile\produtos.html" root@108.174.148.133:/var/www/enviadados/mobile/

echo.
echo Concluido!
pause
