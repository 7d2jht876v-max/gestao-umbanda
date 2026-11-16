@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
 echo Execute INSTALAR.bat primeiro.
 pause
 exit /b 1
)
echo Mantenha esta janela aberta. O endereco do iPhone sera mostrado abaixo.
.venv\Scripts\python.exe server.py --data dados
pause
