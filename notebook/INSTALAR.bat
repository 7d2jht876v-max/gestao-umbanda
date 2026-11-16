@echo off
setlocal
cd /d "%~dp0"
py -3 --version >nul 2>&1
if errorlevel 1 (
 echo Instale primeiro o Python 3.11 ou superior pelo site oficial:
 echo https://www.python.org/downloads/windows/
 echo Marque a opcao de instalar o launcher "py". Depois execute este arquivo novamente.
 pause
 exit /b 1
)
if not exist .venv\Scripts\python.exe py -3 -m venv .venv
if errorlevel 1 goto :erro
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto :erro
.venv\Scripts\python.exe certificates.py --data dados
if errorlevel 1 goto :erro
echo.
echo Certificado local criado. A instalacao abaixo confia SOMENTE no certificado desta pasta.
echo Ele permite HTTPS entre este notebook e o iPhone. Nao compartilhe os arquivos de chave.
choice /C SN /M "Instalar o certificado publico no seu usuario Windows (S/N)"
if errorlevel 2 (
 echo Certificado nao instalado. Siga o guia antes de abrir HTTPS.
 pause
 exit /b 0
)
certutil -user -addstore Root "dados\certificados\CA-Templo-Xango.cer"
if errorlevel 1 goto :erro
echo.
echo Instalacao concluida. Abra INICIAR.bat.
echo Leia LEIA-PRIMEIRO.html para conectar o iPhone.
pause
exit /b 0
:erro
echo.
echo Nao foi possivel concluir a instalacao. Os dados existentes foram mantidos.
echo Fotografe a mensagem acima para obter ajuda.
pause
exit /b 1
