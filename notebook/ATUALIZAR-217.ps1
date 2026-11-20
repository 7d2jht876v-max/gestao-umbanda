param([string]$Pasta = "$env:USERPROFILE\OneDrive\Desktop\Gestao-Umbanda-Notebook")
$ErrorActionPreference = 'Stop'
$Origem = Join-Path $PSScriptRoot 'server.py'
if (-not (Test-Path -LiteralPath $Origem)) { throw 'Arquivo server.py nao encontrado no pacote.' }
if (-not (Test-Path -LiteralPath (Join-Path $Pasta 'server.py'))) { throw "Servidor nao encontrado: $Pasta. Informe a pasta correta." }
if (-not (Test-Path -LiteralPath (Join-Path $Pasta 'dados'))) { throw 'Pasta dados nao encontrada; atualizacao cancelada.' }
if (Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^python(w)?\.exe$' -and $_.CommandLine -match 'server\.py' -and $_.CommandLine -like "*$Pasta*" }) {
    throw 'Servidor em execucao. Feche a janela INICIAR antes de atualizar.'
}
$Backup = Join-Path $Pasta ('backup-codigo-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Path $Backup | Out-Null
Copy-Item -LiteralPath (Join-Path $Pasta 'server.py') -Destination (Join-Path $Backup 'server.py')
Copy-Item -LiteralPath $Origem -Destination (Join-Path $Pasta 'server.py')
Write-Host 'Codigo atualizado. Pasta dados, senhas e certificados nao foram alterados.'
Write-Host "Backup do codigo anterior: $Backup"
Write-Host 'Reinicie o servidor pelo INICIAR.bat. A entrada publica permanece DESATIVADA.'
