@echo off
setlocal enabledelayedexpansion

echo ========================================
echo    Claude Code Skills - Setup
echo ========================================
echo.

:: Step 1: Find Conda
echo [Step 1/4] Finding Conda...

set "CONDA_EXE="

if exist "%USERPROFILE%\miniconda3\Scripts\conda.exe" (
    set "CONDA_EXE=%USERPROFILE%\miniconda3\Scripts\conda.exe"
    goto :found
)
if exist "%USERPROFILE%\anaconda3\Scripts\conda.exe" (
    set "CONDA_EXE=%USERPROFILE%\anaconda3\Scripts\conda.exe"
    goto :found
)

echo     Conda not found
pause
exit /b 1

:found
echo     Found: %CONDA_EXE%

:: Step 2: Check dsbot_env
echo.
echo [Step 2/4] Checking dsbot_env...

"%CONDA_EXE%" env list >"%TEMP%\env_list.txt" 2>&1
findstr "dsbot_env" "%TEMP%\env_list.txt" >/dev/null
if %errorlevel% equ 0 (
    echo     dsbot_env exists
) else (
    echo     Creating dsbot_env...
    "%CONDA_EXE%" create -n dsbot_env python=3.10 -y
)

:: Step 3: Install deps
echo.
echo [Step 3/4] Installing dependencies...
"%CONDA_EXE%" run -n dsbot_env pip install requests beautifulsoup4 lxml PyPDF2 python-docx openai pdfplumber -q

:: Step 4: Save path
echo.
echo [Step 4/4] Saving configuration...
"%CONDA_EXE%" run -n dsbot_env python -c "import sys; print(sys.executable)" >"%TEMP%\python_path.txt" 2>&1
set /p PYTHON_PATH=<"%TEMP%\python_path.txt"

if defined PYTHON_PATH (
    echo %PYTHON_PATH%> "%~dp0..\.python_path"
    echo     Python: %PYTHON_PATH%
)

echo.
echo ========================================
echo    Setup Complete!
echo ========================================
pause
