@echo off
setlocal enabledelayedexpansion

echo ========================================
echo    Common Module Install Script
echo    Create/Update dsbot_env environment
echo ========================================
echo.

:: Step 1: Detect Miniconda
echo [Step 1/3] Detecting Miniconda...

where conda >nul 2>&1
if %errorlevel% equ 0 (
    echo     Found Conda
    goto :env_setup
)

set "MINICONDA_PATH="
if exist "%USERPROFILE%\miniconda3\Scripts\conda.exe" (
    set "MINICONDA_PATH=%USERPROFILE%\miniconda3"
) else if exist "%USERPROFILE%\anaconda3\Scripts\conda.exe" (
    set "MINICONDA_PATH=%USERPROFILE%\anaconda3"
)

if defined MINICONDA_PATH (
    echo     Found Miniconda: !MINICONDA_PATH!
    set "PATH=!MINICONDA_PATH!;!MINICONDA_PATH!\Scripts;!MINICONDA_PATH!\Library\bin;!PATH!"
    goto :env_setup
)

echo     Miniconda not found. Please install from:
echo     https://docs.conda.io/en/latest/miniconda.html
pause
exit /b 1

:env_setup
:: Step 2: Create/Update dsbot_env
echo [Step 2/3] Configuring dsbot_env environment...

set "SCRIPT_DIR=%~dp0"
set "ENV_YML=!SCRIPT_DIR!environment.yml"

conda env list | findstr /C:"dsbot_env" >nul 2>&1
if %errorlevel% equ 0 (
    echo     dsbot_env exists, updating...
    conda env update -n dsbot_env -f "!ENV_YML!" --prune
) else (
    echo     Creating dsbot_env...
    conda env create -f "!ENV_YML!"
)

if %errorlevel% neq 0 (
    echo     Environment setup failed
    pause
    exit /b 1
)

echo     Environment configured

:: Step 3: Install Playwright browser
echo [Step 3/3] Installing Playwright browser...

conda run -n dsbot_env playwright install chromium

if %errorlevel% neq 0 (
    echo     Playwright browser install failed. Run manually:
    echo       conda activate dsbot_env
    echo       playwright install chromium
)

echo.
echo ========================================
echo    Installation Complete!
echo ========================================
echo.
echo Environment: dsbot_env
echo Usage:
echo   conda activate dsbot_env
echo   python xxx.py
echo.

pause