@echo off
title Publicador Automatico GitHub - AegisPulse (Adriano9200)
color 0A

echo ============================================================================
echo    PUBLICADOR GITHUB - AEGISPULSE IT TOOLKIT
echo    Autor: Adriano Barboza (adriano9200@gmail.com)
echo    Repositorio: https://github.com/Adriano9200/AegisPulse-Toolkit.git
echo ============================================================================
echo.

cd /d "%~dp0"

:: Verifica se o Git esta instalado
git --version >nul 2>&1
if %errorLevel% neq 0 (
    echo [ERRO] O Git nao foi encontrado instalado neste computador.
    echo Instale rapidamente rodando no PowerShell: winget install Git.Git
    pause
    exit /b 1
)

echo [1/6] Inicializando repositorio local na branch main...
if not exist ".git" (
    git init
)
git branch -M main

echo [2/6] Configurando assinatura do autor (Adriano Barboza)...
git config user.name "Adriano Barboza"
git config user.email "adriano9200@gmail.com"

echo [3/6] Garantindo bloqueio de arquivos virtuais do Google Drive (.gdoc)...
findstr /C:"*.gdoc" .gitignore >nul 2>&1
if %errorLevel% neq 0 (
    echo.>> .gitignore
    echo *.gdoc>> .gitignore
    echo *.gsheet>> .gitignore
    echo *.gslides>> .gitignore
    echo *.zip>> .gitignore
)

echo [4/6] Vinculando ao repositorio https://github.com/Adriano9200/AegisPulse-Toolkit.git ...
git remote remove origin >nul 2>&1
git remote add origin https://github.com/Adriano9200/AegisPulse-Toolkit.git

echo [5/6] Preparando arquivos e criando commit assinado...
git add .
set COMMIT_MSG=
set /p COMMIT_MSG="Digite a descricao desta atualizacao (ou aperte ENTER para lancamento v1.0.0): "
if "%COMMIT_MSG%"=="" set COMMIT_MSG=feat: lancamento inicial do AegisPulse IT Toolkit v1.0.0 por Adriano Barboza
git commit -m "%COMMIT_MSG%"

echo [6/6] Enviando arquivos para o GitHub (git push)...
git push -u origin main

echo.
echo ============================================================================
echo [FINALIZADO] Confira seu repositorio no navegador:
echo https://github.com/Adriano9200/AegisPulse-Toolkit
echo ============================================================================
pause
