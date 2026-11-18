@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0ATUALIZAR-217.ps1" %*
if errorlevel 1 echo Atualizacao nao concluida. Verifique a mensagem acima.
pause
