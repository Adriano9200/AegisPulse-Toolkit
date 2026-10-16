# ==============================================================================
# AegisPulse IT Toolkit v5.5.0 - Launcher Nativo PowerShell
# Autor: Adriano Barboza (adriano9200@gmail.com | WhatsApp: +55 61 98515-8434)
# ==============================================================================

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$Host.UI.RawUI.WindowTitle = "AegisPulse IT Toolkit v5.5.0 - Por Adriano Barboza"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

# 1. Verifica privilégios de Administrador
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "[AVISO] Executando em modo Usuário Padrão." -ForegroundColor Yellow
    Write-Host "        Para acesso bruto a discos e operações DiskPart, execute o PowerShell como Administrador." -ForegroundColor DarkGray
} else {
    Write-Host "[OK] Privilégios de Administrador detectados." -ForegroundColor Green
}

# 2. Localiza o Python (.venv, python ou py -3)
$PythonExe = $null
if (Test-Path "$ScriptDir\.venv\Scripts\python.exe") {
    $PythonExe = "$ScriptDir\.venv\Scripts\python.exe"
} elseif (Get-Command "python" -ErrorAction SilentlyContinue) {
    $PythonExe = "python"
} elseif (Get-Command "py" -ErrorAction SilentlyContinue) {
    $PythonExe = "py"
}

if (-not $PythonExe) {
    Write-Host "[ERRO] Python 3.10+ não foi encontrado no PATH do Windows nem em .venv!" -ForegroundColor Red
    Write-Host "Instale o Python 3.10+ em https://www.python.org/ marcando 'Add Python to PATH'."
    Read-Host "Pressione ENTER para sair..."
    exit 1
}

Write-Host "[OK] Interpretador Python localizado: $PythonExe" -ForegroundColor Cyan

# 3. Libera porta 8765 se estiver ocupada por instância anterior
try {
    $connections = Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue
    foreach ($conn in $connections) {
        if ($conn.OwningProcess -and $conn.OwningProcess -ne 0) {
            Write-Host "[INFO] Encerrando processo órfão na porta 8765 (PID $($conn.OwningProcess))..." -ForegroundColor Yellow
            Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue
        }
    }
} catch {}

# 4. Inicia o AegisPulse main.py
Write-Host "[OK] Iniciando AegisPulse IT Toolkit v5.5.0..." -ForegroundColor Green
if ($PythonExe -eq "py") {
    & py -3 "$ScriptDir\main.py"
} else {
    & $PythonExe "$ScriptDir\main.py"
}

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERRO] O servidor encerrou com código $LASTEXITCODE." -ForegroundColor Red
    Read-Host "Pressione ENTER para fechar..."
}
