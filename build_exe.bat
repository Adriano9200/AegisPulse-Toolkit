@echo off
chcp 65001 >nul
title Compilador AegisPulse (.EXE Portatil) — Por Adriano Barboza
echo ============================================================================
echo    GERADOR DE EXECUTAVEL PORTATIL — AEGISPULSE IT TOOLKIT
echo    Autor: Adriano Barboza
echo ============================================================================
echo.
pip install pyinstaller psutil
pyinstaller --noconfirm --onefile --windowed --name "AegisPulse_Toolkit" --add-data "frontend;frontend" --add-data "config.example.json;." main.py
echo.
echo [SUCESSO] Executavel criado na pasta: dist\AegisPulse_Toolkit.exe
pause
