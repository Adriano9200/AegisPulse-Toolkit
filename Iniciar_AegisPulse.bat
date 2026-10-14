@echo off
title AegisPulse IT Toolkit - Por Adriano Barboza
color 0B

echo ============================================================================
echo    AEGISPULSE IT TOOLKIT v1.0.0 - DIAGNOSTIC, MAINTENANCE ^& AI SUITE
echo    Autor: Adriano Barboza (adriano9200@gmail.com)
echo ============================================================================
echo.

net session >nul 2>&1
if %errorLevel% == 0 (
    echo [OK] Executando com privilegios de Administrador.
) else (
    echo [AVISO] Solicitando elevacao para Administrador...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

cd /d "%~dp0"

python --version >nul 2>&1
if %errorLevel% neq 0 (
    echo [ERRO] Python 3 nao encontrado no PATH deste computador.
    pause
    exit /b 1
)

echo [INFO] Iniciando servidor local e interface grafica AegisPulse...
python main.py
pause
