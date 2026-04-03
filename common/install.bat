@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ========================================
echo    Common 模块安装脚本
echo    自动创建/更新 dsbot_env 虚拟环境
echo ========================================
echo.

:: ============================================
:: 步骤 1: 检测 Miniconda
:: ============================================
echo [步骤 1/3] 检测 Miniconda...

where conda >nul 2>&1
if %errorlevel% equ 0 (
    echo     √ 已检测到 Conda
    goto :env_setup
)

:: 检测默认安装路径
set "MINICONDA_PATH="
if exist "%USERPROFILE%\miniconda3\Scripts\conda.exe" (
    set "MINICONDA_PATH=%USERPROFILE%\miniconda3"
) else if exist "%USERPROFILE%\anaconda3\Scripts\conda.exe" (
    set "MINICONDA_PATH=%USERPROFILE%\anaconda3"
)

if defined MINICONDA_PATH (
    echo     √ 已检测到 Miniconda: !MINICONDA_PATH!
    set "PATH=!MINICONDA_PATH!;!MINICONDA_PATH!\Scripts;!MINICONDA_PATH!\Library\bin;!PATH!"
    goto :env_setup
)

echo     × 未检测到 Miniconda，请先安装
echo     下载地址: https://docs.conda.io/en/latest/miniconda.html
pause
exit /b 1

:env_setup
:: ============================================
:: 步骤 2: 创建/更新 dsbot_env 环境
:: ============================================
echo [步骤 2/3] 配置 dsbot_env 环境...

set "SCRIPT_DIR=%~dp0"
set "ENV_YML=!SCRIPT_DIR!environment.yml"

:: 检查环境是否存在
conda env list | findstr /C:"dsbot_env" >nul 2>&1
if %errorlevel% equ 0 (
    echo     dsbot_env 环境已存在，正在更新...
    conda env update -n dsbot_env -f "!ENV_YML!" --prune
) else (
    echo     创建 dsbot_env 环境...
    conda env create -f "!ENV_YML!"
)

if %errorlevel% neq 0 (
    echo     × 环境配置失败
    pause
    exit /b 1
)

echo     √ 环境配置完成

:: ============================================
:: 步骤 3: 安装 Playwright 浏览器
:: ============================================
echo [步骤 3/3] 安装 Playwright 浏览器...

conda run -n dsbot_env playwright install chromium

if %errorlevel% neq 0 (
    echo     ! Playwright 浏览器安装失败，请手动运行:
    echo       conda activate dsbot_env
    echo       playwright install chromium
)

echo.
echo ========================================
echo    安装完成！
echo ========================================
echo.
echo 虚拟环境: dsbot_env
echo 使用方法:
echo   conda activate dsbot_env
echo   python xxx.py
echo.

pause