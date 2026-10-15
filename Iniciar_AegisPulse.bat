@echo off
chcp 65001 >nul
title AegisPulse IT Toolkit v4.5 - Por Adriano Barboza
cd /d "%~dp0"

echo ============================================================================
echo   AEGISPULSE IT TOOLKIT v4.5 - Health Score + Storage Forensics + Multi-IA
echo   Desenvolvido por Adriano Barboza ^| WhatsApp: +55 61 98515-8434
echo ============================================================================
echo.

REM 1. Encerra qualquer instancia anterior presa na porta 8765
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8765 ^| findstr LISTENING') do taskkill /F /PID %%a >nul 2>&1

REM 2. Verifica se o Python esta disponivel
where python >nul 2>&1
if errorlevel 1 goto :NO_PYTHON

REM 3. Garante que o psutil esteja instalado
python -c "import psutil" >nul 2>&1
if errorlevel 1 python -m pip install psutil --quiet

echo [OK] Iniciando servidor local em http://127.0.0.1:8765 - Janela Propria App...
echo [DICA] Senhas Master ADM aceitas: Luna@19102023 ^| Luna@10192023 ^| admin123
echo.

REM 4. Inicia o servidor principal (o main.py abre SOMENTE a janela dedicada --app)
python main.py
if errorlevel 1 pause
exit /b 0

:NO_PYTHON
echo [ERRO] Python nao encontrado no PATH do Windows!
echo Instale o Python 3.10+ em https://www.python.org/ e marque "Add Python to PATH".
pause
exit /b 1
