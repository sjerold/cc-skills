@echo off
setlocal enabledelayedexpansion

echo ========================================
echo    Baidu Search Plugin - Setup
echo ========================================
echo.

:: Check Conda
where conda >/dev/null 2>&1
if %errorlevel% neq 0 (
    :: Check default paths
    if exist "%USERPROFILE%\miniconda3\Scripts\conda.exe" (
        set "PATH=%USERPROFILE%\miniconda3;%USERPROFILE%\miniconda3\Scripts;%PATH%"
    ) else if exist "%USERPROFILE%\anaconda3\Scripts\conda.exe" (
        set "PATH=%USERPROFILE%\anaconda3;%USERPROFILE%\anaconda3\Scripts;%PATH%"
    ) else (
        echo Miniconda not found, downloading...
        curl -L -o "%TEMP%\Miniconda3-latest.exe" https://repo.anaconda.com/miniconda/Miniconda3-latest-Windows-x86_64.exe
        if exist "%TEMP%\Miniconda3-latest.exe" (
            echo Installing Miniconda...
            start /wait "" "%TEMP%\Miniconda3-latest.exe" /InstallationType=JustMe /RegisterPython=1 /AddToPath=1 /S /D=%USERPROFILE%\miniconda3
            set "PATH=%USERPROFILE%\miniconda3;%USERPROFILE%\miniconda3\Scripts;%PATH%"
            del "%TEMP%\Miniconda3-latest.exe" 2>/dev/null
            echo Miniconda installed
        ) else (
            echo Download failed, please install Miniconda manually
            pause
            exit /b 1
        )
    )
)

:: Init conda
call conda activate base 2>/dev/null || call "%USERPROFILE%\miniconda3\Scripts\activate.bat" 2>/dev/null

:: Check dsbot_env
conda env list 2>/dev/null | findstr "dsbot_env" >/dev/null
if %errorlevel% neq 0 (
    echo Creating dsbot_env environment...
    conda create -n dsbot_env python=3.10 -y
    if %errorlevel% neq 0 (
        echo Failed to create environment
        pause
        exit /b 1
    )
)

:: Install dependencies
echo Installing dependencies...
conda run -n dsbot_env pip install requests beautifulsoup4 PyPDF2 python-docx -q

:: Get Python path
for /f "tokens=*" %%i in ('conda run -n dsbot_env python -c "import sys; print(sys.executable)" 2^^^>nul') do set "PYTHON_PATH=%%i"

:: Save path
echo !PYTHON_PATH!> "%~dp0..\.python_path"
setx CONDA_PYTHON "!PYTHON_PATH!" >/dev/null 2>&1

echo.
echo ========================================
echo    Setup Complete!
echo ========================================
echo Python: !PYTHON_PATH!
echo.
pause
