@echo off
setlocal enabledelayedexpansion

echo ========================================
echo    Claude Code Skills - Setup
echo ========================================
echo.

:: Step 1: Find Conda
echo [Step 1/4] Finding Conda...

set "CONDA_ROOT="

if exist "%USERPROFILE%\miniconda3\Scripts\conda.exe" (
    set "CONDA_ROOT=%USERPROFILE%\miniconda3"
    goto :found_conda
)
if exist "%USERPROFILE%\anaconda3\Scripts\conda.exe" (
    set "CONDA_ROOT=%USERPROFILE%\anaconda3"
    goto :found_conda
)
if exist "C:\ProgramData\miniconda3\Scripts\conda.exe" (
    set "CONDA_ROOT=C:\ProgramData\miniconda3"
    goto :found_conda
)

echo     Conda not found, downloading...
curl -L -o "%TEMP%\Miniconda3.exe" https://repo.anaconda.com/miniconda/Miniconda3-latest-Windows-x86_64.exe
if exist "%TEMP%\Miniconda3.exe" (
    echo     Installing...
    start /wait "" "%TEMP%\Miniconda3.exe" /InstallationType=JustMe /RegisterPython=1 /AddToPath=1 /S /D=%USERPROFILE%\miniconda3
    set "CONDA_ROOT=%USERPROFILE%\miniconda3"
    del "%TEMP%\Miniconda3.exe"
)

:found_conda
if not defined CONDA_ROOT (
    echo     ERROR: Conda not found!
    pause
    exit /b 1
)
echo     Found: %CONDA_ROOT%
set "PATH=%CONDA_ROOT%;%CONDA_ROOT%\Scripts;%CONDA_ROOT%\Library\bin;%PATH%"

:: Step 2: Check dsbot_env
echo.
echo [Step 2/4] Checking dsbot_env...
"%CONDA_ROOT%\Scripts\conda.exe" env list | findstr "dsbot_env" >/dev/null
if %errorlevel% equ 0 (
    echo     dsbot_env exists
) else (
    echo     Creating dsbot_env...
    "%CONDA_ROOT%\Scripts\conda.exe" create -n dsbot_env python=3.10 -y
)

:: Step 3: Install deps
echo.
echo [Step 3/4] Installing dependencies...
"%CONDA_ROOT%\Scripts\conda.exe" run -n dsbot_env pip install requests beautifulsoup4 lxml PyPDF2 python-docx openai pdfplumber -q

:: Step 4: Save path
echo.
echo [Step 4/4] Saving configuration...
for /f "tokens=*" %%i in ('"%CONDA_ROOT%\Scripts\conda.exe" run -n dsbot_env python -c "import sys; print(sys.executable)" 2^^^>nul') do set "PY=%%i"
if defined PY (
    echo %PY%> "%~dp0..\.python_path"
    setx CONDA_PYTHON "%PY%" >/dev/null 2>&1
    echo     Python: %PY%
)

echo.
echo ========================================
echo    Setup Complete!
echo ========================================
echo Use: /baidu-search
pause
