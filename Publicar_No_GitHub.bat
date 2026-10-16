@echo off
title Publicador Automatico GitHub - AegisPulse v4.0 (Adriano9200)
color 0A

echo ============================================================================
echo    PUBLICADOR GITHUB - AEGISPULSE IT TOOLKIT v4.0.0
echo    Autor: Adriano Barboza (adriano9200@gmail.com)
echo    Repositorio: https://github.com/Adriano9200/AegisPulse-Toolkit.git
echo ============================================================================
echo.

cd /d "%~dp0"

:: 1. Sincroniza arquivos do Google Drive se executado em D:\PROJETOS_PESSOAL
if exist "G:\Meu Drive\AegisPulse-Toolkit" (
    echo [0/6] Copiando arquivos atualizados do Google Drive para a pasta local...
    robocopy "G:\Meu Drive\AegisPulse-Toolkit" "%~dp0." /E /XD .git __pycache__ data reports logs /XF *.gdoc *.gsheet *.old *.v1_1_old *.v2.old *.v3.old *.v3_0_0.old config.json license.json >nul 2>&1
)

:: 2. Verifica se o Git esta instalado
git --version >nul 2>&1
if %errorLevel% neq 0 (
    echo [ERRO] O Git nao foi encontrado instalado neste computador.
    echo Instale rapidamente rodando no PowerShell: winget install Git.Git
    pause
    exit /b 1
)

echo [1/6] Configurando repositorio local e branch main...
if not exist ".git" (
    git init
)
git branch -M main

echo [2/6] Configurando identidade oficial do autor...
git config user.name "Adriano Barboza"
git config user.email "adriano9200@gmail.com"

echo [3/6] Conectando ao repositorio remoto...
git remote remove origin >nul 2>&1
git remote add origin https://github.com/Adriano9200/AegisPulse-Toolkit.git

echo [4/6] Sincronizando com o GitHub (pull)...
git pull origin main --rebase >nul 2>&1

echo [5/6] Adicionando arquivos e criando commit...
git add -A
git status --short

set COMMIT_MSG=feat(storage): lancamento AegisPulse v4.0.0 com modulo forense de discos, SMART profundo, vida util SQLite, testes de integridade e recuperacao assistida por Adriano Barboza
git commit -m "%COMMIT_MSG%" >nul 2>&1

echo [6/6] Enviando atualizacoes para o GitHub (git push)...
git push -u origin main

echo.
echo ============================================================================
echo [FINALIZADO] Confira seu repositorio atualizado no navegador:
echo https://github.com/Adriano9200/AegisPulse-Toolkit
echo ============================================================================
pause
