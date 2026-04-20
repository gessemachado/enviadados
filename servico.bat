@echo off
setlocal
set NOME=SyncAgent
set EXE=%~dp0SyncAgent.exe

if "%1"=="instalar" goto instalar
if "%1"=="remover"  goto remover
if "%1"=="iniciar"  goto iniciar
if "%1"=="parar"    goto parar
if "%1"=="status"   goto status

echo Uso: servico.bat [instalar^|remover^|iniciar^|parar^|status]
goto fim

:instalar
sc create %NOME% binPath= "%EXE%" start= auto DisplayName= "SyncAgent Firebird-Supabase"
sc description %NOME% "Sincroniza dados do Firebird para o Supabase a cada 15 minutos"
sc start %NOME%
echo Servico instalado e iniciado.
goto fim

:remover
sc stop %NOME%
sc delete %NOME%
echo Servico removido.
goto fim

:iniciar
sc start %NOME%
goto fim

:parar
sc stop %NOME%
goto fim

:status
sc query %NOME%
goto fim

:fim
endlocal
