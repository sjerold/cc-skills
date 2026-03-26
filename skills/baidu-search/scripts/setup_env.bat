@echo off
setlocal enabledelayedexpansion

echo ========================================
echo    Claude Code Skills - Setup
echo ========================================
echo.

:: Step 1: Find Conda
echo [Step 1/4] Finding Conda...

set "CONDA_CMD="

:: Check common paths
for %%p in (
    "%USERPROFILE%\miniconda3"
    "%USERPROFILE%\anaconda3"  
    "C:\ProgramData\miniconda3"
) do (
    if exist "%%~p\Scripts\conda.exe" (
        set "CONDA_ROOT=%%~p"
        set "CONDA_CMD=%%~p\Scripts\conda.exe"
        goto :found_conda
    )
)

echo     Conda not found, downloading...
curl -L -o "%TEMP%\Miniconda3.exe" https://repo.anaconda.com/miniconda/Miniconda3-latest-Windows-x86_64.exe
if exist "%TEMP%\Miniconda3.exe" (
    echo     Installing...
    start /wait "" "%TEMP%\Miniconda3.exe" /InstallationType=JustMe /RegisterPython=1 /AddToPath=1 /S /D=%USERPROFILE%\miniconda3
    set "CONDA_ROOT=%USERPROFILE%\miniconda3"
    set "CONDA_CMD=%USERPROFILE%\miniconda3\Scripts\conda.exe"
    del "%TEMP%\Miniconda3.exe"
)

:found_conda
if not defined CONDA_CMD (
    echo     ERROR: Conda not found!
    echo     Please install from: https://docs.conda.io/en/latest/miniconda.html
    pause
    exit /b 1
)
echo     Found: %CONDA_ROOT%

:: Step 2: Check dsbot_env
echo.
echo [Step 2/4] Checking dsbot_env...

"%CONDA_CMD%" env list 2>/dev/null | findstr /C:"dsbot_env" >/dev/null
if %errorlevel% equ 0 (
    echo     dsbot_env exists
    set "ENV_EXISTS=1"
) else (
    echo     Creating dsbot_env...
    "%CONDA_CMD%" create -n dsbot_env python=3.10 -y
    if !errorlevel! neq 0 (
        echo     Failed to create environment
        pause
        exit /b 1
    )
    set "ENV_EXISTS=0"
)

:: Step 3: Install deps
echo.
echo [Step 3/4] Installing dependencies...
"%CONDA_CMD%" run -n dsbot_env pip install requests beautifulsoup4 lxml PyPDF2 python-docx openai pdfplumber -q 2>/dev/null

:: Step 4: Save path
echo.
echo [Step 4/4] Saving configuration...
for /f "usebackq tokens=*" %%i in (`"%CONDA_CMD%" run -n dsbot_env python -c "import sys; print(sys.executable)"`) do set "PY=%%i"

if defined PY (
    echo !PY!> "%~dp0..\.python_path"
    setx CONDA_PYTHON "!PY!" >/dev/null 2>&1
    echo     Python: !PY!
)

echo.
echo ========================================
echo    Setup Complete!
echo ========================================
echo.
echo Use: /baidu-search
echo.
pause
