@echo off
chcp 65001 >/dev/null
setlocal enabledelayedexpansion

echo ========================================
echo    百度搜索插件 - 环境安装
echo ========================================
echo.

:: 检测 Conda
where conda >/dev/null 2>&1
if %errorlevel% neq 0 (
    :: 检测默认路径
    if exist "%USERPROFILE%\miniconda3\Scripts\conda.exe" (
        set "PATH=%USERPROFILE%\miniconda3;%USERPROFILE%\miniconda3\Scripts;%PATH%"
    ) else (
        echo 未检测到 Miniconda，正在下载安装...
        curl -L -o "%TEMP%\Miniconda3-latest.exe" https://repo.anaconda.com/miniconda/Miniconda3-latest-Windows-x86_64.exe
        start /wait "" "%TEMP%\Miniconda3-latest.exe" /InstallationType=JustMe /RegisterPython=1 /AddToPath=1 /S /D=%USERPROFILE%\miniconda3
        set "PATH=%USERPROFILE%\miniconda3;%USERPROFILE%\miniconda3\Scripts;%PATH%"
        del "%TEMP%\Miniconda3-latest.exe" 2>/dev/null
    )
)

:: 检测 dsbot_env
conda env list | findstr "dsbot_env" >/dev/null 2>&1
if %errorlevel% neq 0 (
    echo 正在创建 dsbot_env 环境...
    conda create -n dsbot_env python=3.10 -y
)

:: 安装依赖
echo 正在安装依赖...
conda run -n dsbot_env pip install requests beautifulsoup4 PyPDF2 python-docx -q

:: 获取 Python 路径
for /f "tokens=*" %%i in ('conda run -n dsbot_env python -c "import sys; print(sys.executable)"') do set "PYTHON_PATH=%%i"

:: 保存路径
echo !PYTHON_PATH!> "%~dp0..\.python_path"
setx CONDA_PYTHON "!PYTHON_PATH!" >/dev/null 2>&1

echo.
echo ========================================
echo    安装完成！
echo ========================================
echo Python: !PYTHON_PATH!
echo.
echo 现在可以使用 /baidu-search 命令了
pause
