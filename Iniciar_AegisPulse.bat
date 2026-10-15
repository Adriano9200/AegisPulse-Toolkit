@echo off
title AegisPulse IT Toolkit - Por Adriano Barboza
color 0B

echo ============================================================================
echo    AEGISPULSE IT TOOLKIT v4.5 - DIAGNOSTIC, HEALTH SCORE ^& AI SUITE
echo    Autor: Adriano Barboza (adriano9200@gmail.com)
echo    WhatsApp Comercial: +55 61 98515-8434
echo ============================================================================
echo.

cd /d "%~dp0"

:: 1. Verifica privilégios de Administrador (opcional, continua normalmente se não elevado)
net session >nul 2>&1
if %errorLevel% == 0 (
    echo [OK] Executando com privilegios de Administrador.
) else (
    echo [INFO] Dica: Para leitura fisica SMART e reparos avancados,
    echo        recomenda-se clicar com o botao direito e "Executar como Administrador".
)

:: 2. Verifica se o Python esta instalado
python --version >nul 2>&1
if %errorLevel% neq 0 (
    echo [ERRO] Python 3 nao encontrado no PATH deste computador.
    echo Instale o Python pelo site oficial python.org ou via winget: winget install Python.Python.3.12
    pause
    exit /b 1
)

:: 3. Encerra processos orfaos que possam estar prendendo a porta 8765
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8765 ^| findstr LISTENING') do (
    echo [AVISO] Liberando porta 8765 ocupada pelo processo PID %%a...
    taskkill /f /pid %%a >nul 2>&1
)

:: 4. Abre o navegador na URL do AegisPulse apos 2 segundos
start "" cmd /c "timeout /t 2 /nobreak >nul & start http://127.0.0.1:8765"

:: 5. Inicia o servidor Python
echo [INFO] Servidor iniciando em http://127.0.0.1:8765 ...
python main.py

echo.
echo [INFO] Servidor encerrado.
pause
