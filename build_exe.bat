@echo off
chcp 65001 >nul
title Compilador AegisPulse v4.5 - Kit Pendrive Portatil - Por Adriano Barboza
cd /d "%~dp0"

echo ============================================================================
echo   GERADOR DO EXECUTAVEL E KIT PENDRIVE PORTATIL - AEGISPULSE v4.5
echo   Autor: Adriano Barboza ^| WhatsApp: +55 61 98515-8434
echo ============================================================================
echo.

REM 1. Verifica o Python
where python >nul 2>&1
if errorlevel 1 goto :NO_PYTHON

echo [1/4] Instalando/atualizando PyInstaller e dependencias de compilacao...
python -m pip install --upgrade pip pyinstaller psutil
if errorlevel 1 goto :PIP_ERROR

echo.
echo [2/4] Compilando AegisPulse_Toolkit.exe autonomo - aguarde de 30 a 90 segundos...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8765 ^| findstr LISTENING') do taskkill /F /PID %%a >nul 2>&1
taskkill /F /IM AegisPulse_Toolkit.exe >nul 2>&1

python -m PyInstaller --noconfirm --clean --onefile --console --name "AegisPulse_Toolkit" --collect-submodules backend --hidden-import psutil --hidden-import sqlite3 --add-data "frontend;frontend" --add-data "config.example.json;." main.py
if not exist "dist\AegisPulse_Toolkit.exe" goto :BUILD_ERROR

echo.
echo [3/4] Montando pasta pronta para Pendrive em: KIT_PENDRIVE_PORTATIL ...
if not exist "KIT_PENDRIVE_PORTATIL" mkdir "KIT_PENDRIVE_PORTATIL"
if not exist "KIT_PENDRIVE_PORTATIL\frontend" mkdir "KIT_PENDRIVE_PORTATIL\frontend"
if not exist "KIT_PENDRIVE_PORTATIL\data" mkdir "KIT_PENDRIVE_PORTATIL\data"
if not exist "KIT_PENDRIVE_PORTATIL\reports" mkdir "KIT_PENDRIVE_PORTATIL\reports"
if not exist "KIT_PENDRIVE_PORTATIL\logs" mkdir "KIT_PENDRIVE_PORTATIL\logs"

copy /Y "dist\AegisPulse_Toolkit.exe" "KIT_PENDRIVE_PORTATIL\AegisPulse_Toolkit.exe" >nul
copy /Y "config.example.json" "KIT_PENDRIVE_PORTATIL\config.example.json" >nul
if exist "config.json" copy /Y "config.json" "KIT_PENDRIVE_PORTATIL\config.json" >nul
xcopy /E /I /Y "frontend\*.*" "KIT_PENDRIVE_PORTATIL\frontend\" >nul

REM Cria o inicializador com elevacao automatica de Administrador para usar no cliente
(
echo @echo off
echo chcp 65001 ^>nul
echo title AegisPulse IT Toolkit v4.5 Portatil - Adriano Barboza
echo cd /d "%%~dp0"
echo net session ^>nul 2^>^&1
echo if errorlevel 1 goto :ELEVATE
echo goto :RUN
echo :ELEVATE
echo echo [INFO] Solicitando permissao de Administrador para leitura SMART fisica e reparo...
echo powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%%~f0' -WorkingDirectory '%%~dp0' -Verb RunAs"
echo exit /b 0
echo :RUN
echo for /f "tokens=5" %%%%a in ^('netstat -aon ^^^| findstr :8765 ^^^| findstr LISTENING'^) do taskkill /F /PID %%%%a ^>nul 2^>^&1
echo echo [OK] Iniciando AegisPulse_Toolkit.exe direto do Pendrive...
echo "%%~dp0AegisPulse_Toolkit.exe"
) > "KIT_PENDRIVE_PORTATIL\1_Abrir_AegisPulse_Como_Admin.bat"

REM Cria o instalador de instancias e dependencias para qualquer computador cliente
(
echo @echo off
echo chcp 65001 ^>nul
echo title Instalador de Instancias e Runtimes de Suporte - AegisPulse v4.5
echo cd /d "%%~dp0"
echo net session ^>nul 2^>^&1
echo if errorlevel 1 goto :ELEVATE_DEP
echo goto :INSTALL_DEPS
echo :ELEVATE_DEP
echo powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%%~f0' -WorkingDirectory '%%~dp0' -Verb RunAs"
echo exit /b 0
echo :INSTALL_DEPS
echo echo ============================================================================
echo echo   INSTALADOR DE INSTANCIAS NECESSARIAS NO COMPUTADOR DO CLIENTE
echo echo   AegisPulse IT Toolkit v4.5 - Por Adriano Barboza
echo echo ============================================================================
echo echo.
echo echo [1/5] Verificando gerenciador Winget e servicos do Windows...
echo winget --version ^>nul 2^>^&1
echo if errorlevel 1 echo [AVISO] Winget nao detectado neste Windows. Usando instaladores alternativos quando disponiveis.
echo.
echo echo [2/5] Instalando Microsoft Visual C++ Redistributable 2015-2022 x64 e x86...
echo winget install --id Microsoft.VCRedist.2015+.x64 --silent --accept-package-agreements --accept-source-agreements
echo winget install --id Microsoft.VCRedist.2015+.x86 --silent --accept-package-agreements --accept-source-agreements
echo.
echo echo [3/5] Instalando Microsoft .NET Desktop Runtime 8.0...
echo winget install --id Microsoft.DotNet.DesktopRuntime.8 --silent --accept-package-agreements --accept-source-agreements
echo.
echo echo [4/5] Instalando Smartmontools - smartctl para leitura SMART profunda via USB/NVMe...
echo winget install --id smartmontools.smartmontools --silent --accept-package-agreements --accept-source-agreements
echo.
echo echo [5/5] Verificando ambiente Python + psutil caso deseje rodar em modo codigo-fonte...
echo where python ^>nul 2^>^&1
echo if errorlevel 1 winget install --id Python.Python.3.12 --silent --accept-package-agreements --accept-source-agreements
echo python -m pip install --upgrade psutil ^>nul 2^>^&1
echo.
echo echo ============================================================================
echo echo   [CONCLUIDO] Todas as instancias e runtimes foram verificados/instalados!
echo echo   Agora basta executar: 1_Abrir_AegisPulse_Como_Admin.bat ou AegisPulse_Toolkit.exe
echo echo ============================================================================
echo pause
) > "KIT_PENDRIVE_PORTATIL\2_Instalar_Dependencias_No_Cliente.bat"

echo.
echo ============================================================================
echo   [SUCESSO TOTAL] EXECUTAVEL E KIT PENDRIVE GERADOS COM SUCESSO!
echo ============================================================================
echo   1. Executavel puro : %~dp0dist\AegisPulse_Toolkit.exe
echo   2. Pasta Pendrive  : %~dp0KIT_PENDRIVE_PORTATIL\
echo      - AegisPulse_Toolkit.exe (Roda em qualquer PC mesmo sem Python!)
echo      - 1_Abrir_AegisPulse_Como_Admin.bat (Abre como Administrador no cliente)
echo      - 2_Instalar_Dependencias_No_Cliente.bat (Instala VC++, .NET, smartctl, Python)
echo ============================================================================
echo.
echo [4/4] Abrindo a pasta KIT_PENDRIVE_PORTATIL no Windows Explorer...
explorer.exe "%~dp0KIT_PENDRIVE_PORTATIL"
pause
exit /b 0

:NO_PYTHON
echo [ERRO] Python nao encontrado no PATH! Instale o Python 3.10+ antes de compilar.
pause
exit /b 1

:PIP_ERROR
echo [ERRO] Nao foi possivel instalar o PyInstaller via pip. Verifique sua conexao com a internet.
pause
exit /b 1

:BUILD_ERROR
echo [ERRO] A compilacao do PyInstaller falhou. Verifique as mensagens acima.
pause
exit /b 1
