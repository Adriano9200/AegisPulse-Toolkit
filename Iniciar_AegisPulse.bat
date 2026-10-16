@echo off
setlocal EnableExtensions
chcp 65001 >nul
title AegisPulse IT Toolkit v5.1 - Por Adriano Barboza
cd /d "%~dp0"

echo ============================================================================
echo   AEGISPULSE IT TOOLKIT v5.1 - Diagnostico, Health Score ^& Seguranca de Disco
echo   Desenvolvido por Adriano Barboza ^| WhatsApp: +55 61 98515-8434
echo ============================================================================
echo.

REM 1. Verifica privilegios de Administrador sem fechar o terminal do usuario
net session >nul 2>&1
if errorlevel 1 (
    echo [AVISO] Executando em modo Usuario Padrao.
    echo         Para leitura fisica bruta e operacoes DiskPart em discos externos,
    echo         recomenda-se abrir o PowerShell/CMD como Administrador.
) else (
    echo [OK] Privilegios de Administrador detectados.
)
echo.

REM 2. Localiza o interpretador Python (.venv local, python no PATH ou py launcher)
set "PYTHON_EXE="
if exist "%~dp0.venv\Scripts\python.exe" set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
if defined PYTHON_EXE goto :PYTHON_FOUND

where python >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_EXE=python"
    goto :PYTHON_FOUND
)

where py >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_EXE=py -3"
    goto :PYTHON_FOUND
)

echo [ERRO] Python 3.10+ nao foi encontrado no PATH do Windows nem em .venv!
echo Instale o Python 3.10+ em https://www.python.org/ e marque "Add Python to PATH".
pause
exit /b 1

:PYTHON_FOUND
echo [OK] Interpretador Python localizado: %PYTHON_EXE%

REM 3. Verifica dependencias obrigatorias sem reinstalar pacotes desnecessariamente
%PYTHON_EXE% -c "import psutil" >nul 2>&1
if errorlevel 1 (
    echo [INFO] Dependencia 'psutil' ausente. Instalando pacote necessario...
    %PYTHON_EXE% -m pip install "psutil>=5.9.0" --quiet
    if errorlevel 1 (
        echo [AVISO] Nao foi possivel instalar 'psutil' automaticamente. Verifique sua conexao.
    )
) else (
    echo [OK] Dependencias verificadas sem necessidade de reinstalacao.
)

REM 4. Verifica se ja existe uma instancia antiga ocupando a porta 8765
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8765 ^| findstr LISTENING') do (
    if not "%%a"=="0" (
        echo [INFO] Liberando instancia anterior na porta 8765 - PID %%a...
        taskkill /F /PID %%a >nul 2>&1
    )
)

echo [OK] Iniciando servidor local e abrindo somente a janela dedicada do aplicativo...
echo.

REM 5. Inicia o orquestrador principal tratando caminhos com espacos
%PYTHON_EXE% "%~dp0main.py"
set "EXIT_CODE=%errorlevel%"
if not "%EXIT_CODE%"=="0" (
    echo.
    echo [ERRO] O servidor encerrou com codigo %EXIT_CODE%. Revise as mensagens acima.
    pause
)
endlocal
exit /b %EXIT_CODE%
