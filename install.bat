@echo off
chcp 65001 >/dev/null
setlocal enabledelayedexpansion

echo ========================================
echo    Claude Code Skill 安装脚本
echo    支持 Miniconda 自动安装
echo ========================================
echo.

set "SCRIPT_DIR=%~dp0"
set "SKILL_NAME="
set "SKILL_DIR="

:: 检测当前目录是否是 skill 目录
if exist "%SCRIPT_DIR%SKILL.md" (
    for %%I in ("%SCRIPT_DIR:~0,-1%") do set "SKILL_NAME=%%~nxI"
    set "SKILL_DIR=%SCRIPT_DIR%"
) else if exist "%SCRIPT_DIR%skills" (
    echo 可用 Skill:
    echo.
    set /a count=0
    for /d %%d in ("%SCRIPT_DIR%skills\*") do (
        set /a count+=1
        echo   !count!. %%~nd
    )
    echo.
    set /p choice="请输入要安装的 Skill 编号: "
    set /a count=0
    for /d %%d in ("%SCRIPT_DIR%skills\*") do (
        set /a count+=1
        if !count! equ !choice! (
            set "SKILL_NAME=%%~nd"
            set "SKILL_DIR=%SCRIPT_DIR%skills\%%~nd"
        )
    )
)

if "!SKILL_NAME!"=="" (
    echo × 无法确定要安装的 Skill
    pause
    exit /b 1
)

echo 检测到 Skill: !SKILL_NAME!
echo.

:: ============================================
:: 步骤 1: 检测或安装 Miniconda
:: ============================================
echo [步骤 1/4] 检测 Miniconda/Anaconda...

:: 检测 conda 是否已安装
where conda >/dev/null 2>&1
if %errorlevel% equ 0 (
    echo     √ 已检测到 Conda
    for /f "tokens=*" %%i in ('conda --version') do set CONDA_VERSION=%%i
    echo     版本: !CONDA_VERSION!
    goto :env_setup
)

:: 检测默认安装路径
set "MINICONDA_PATH="
if exist "%USERPROFILE%\miniconda3\Scripts\conda.exe" (
    set "MINICONDA_PATH=%USERPROFILE%\miniconda3"
) else if exist "%USERPROFILE%\anaconda3\Scripts\conda.exe" (
    set "MINICONDA_PATH=%USERPROFILE%\anaconda3"
) else if exist "C:\ProgramData\miniconda3\Scripts\conda.exe" (
    set "MINICONDA_PATH=C:\ProgramData\miniconda3"
)

if defined MINICONDA_PATH (
    echo     √ 已检测到 Miniconda: !MINICONDA_PATH!
    set "PATH=!MINICONDA_PATH!;!MINICONDA_PATH!\Scripts;!MINICONDA_PATH!\Library\bin;!PATH!"
    goto :env_setup
)

:: 需要安装 Miniconda
echo     ! 未检测到 Miniconda
echo.
set /p install_miniconda="是否自动下载安装 Miniconda? (Y/N): "
if /i "!install_miniconda!" neq "Y" (
    echo.
    echo 请手动安装 Miniconda 后重试:
    echo   下载地址: https://docs.conda.io/en/latest/miniconda.html
    pause
    exit /b 1
)

echo.
echo     正在下载 Miniconda...
set "MINICONDA_INSTALLER=%TEMP%\Miniconda3-latest-Windows-x86_64.exe"
curl -L -o "%MINICONDA_INSTALLER%" https://repo.anaconda.com/miniconda/Miniconda3-latest-Windows-x86_64.exe

if not exist "%MINICONDA_INSTALLER%" (
    echo     × 下载失败
    pause
    exit /b 1
)

echo     正在安装 Miniconda (静默安装)...
start /wait "" "%MINICONDA_INSTALLER%" /InstallationType=JustMe /RegisterPython=1 /AddToPath=1 /S /D=%USERPROFILE%\miniconda3

:: 清理安装程序
del "%MINICONDA_INSTALLER%" 2>/dev/null

:: 设置环境变量
set "MINICONDA_PATH=%USERPROFILE%\miniconda3"
set "PATH=!MINICONDA_PATH!;!MINICONDA_PATH!\Scripts;!MINICONDA_PATH!\Library\bin;!PATH!"

echo     √ Miniconda 安装完成
echo.

:env_setup
:: ============================================
:: 步骤 2: 创建/更新 dsbot_env 环境
:: ============================================
echo [步骤 2/4] 配置 dsbot_env 环境...

:: 检查环境是否存在
conda env list | findstr /C:"dsbot_env" >/dev/null 2>&1
if %errorlevel% equ 0 (
    echo     √ dsbot_env 环境已存在
    set /p update_env="是否更新环境依赖? (Y/N): "
    if /i "!update_env!"=="Y" (
        if exist "!SKILL_DIR!\environment.yml" (
            echo     正在更新环境...
            conda env update -n dsbot_env -f "!SKILL_DIR!\environment.yml" --prune
        ) else if exist "!SKILL_DIR!\requirements.txt" (
            echo     正在更新依赖...
            conda run -n dsbot_env pip install -r "!SKILL_DIR!\requirements.txt"
        )
    )
) else (
    echo     ! dsbot_env 环境不存在，正在创建...
    if exist "!SKILL_DIR!\environment.yml" (
        conda env create -f "!SKILL_DIR!\environment.yml"
    ) else (
        conda create -n dsbot_env python=3.10 -y
        if exist "!SKILL_DIR!\requirements.txt" (
            conda run -n dsbot_env pip install -r "!SKILL_DIR!\requirements.txt"
        )
    )
)

if %errorlevel% neq 0 (
    echo     × 环境创建失败
    pause
    exit /b 1
)
echo     √ 环境配置完成
echo.

:: ============================================
:: 步骤 3: 设置环境变量
:: ============================================
echo [步骤 3/4] 配置环境变量...

:: 获取 dsbot_env 的 Python 路径
for /f "tokens=*" %%i in ('conda run -n dsbot_env python -c "import sys; print(sys.executable)"') do set "CONDA_PYTHON=%%i"
echo     Python: !CONDA_PYTHON!

:: 设置用户环境变量 (持久化)
setx CONDA_PYTHON "!CONDA_PYTHON!" >/dev/null 2>&1
echo     √ 已设置 CONDA_PYTHON 环境变量
echo.

:: ============================================
:: 步骤 4: 安装插件文件
:: ============================================
echo [步骤 4/4] 安装插件文件...

set "TARGET_DIR=%USERPROFILE%\.claude\plugins\!SKILL_NAME!"
echo     目标目录: !TARGET_DIR!

if not exist "!TARGET_DIR!" mkdir "!TARGET_DIR!"
xcopy /e /i /y "!SKILL_DIR!\*" "!TARGET_DIR!\" >/dev/null

:: 写入 Python 路径到配置文件
echo !CONDA_PYTHON!> "!TARGET_DIR!\.python_path"

echo     √ 插件文件已复制
echo.

:: ============================================
:: 完成
:: ============================================
echo ========================================
echo    安装完成！
echo ========================================
echo.
echo Skill: !SKILL_NAME!
echo 安装位置: !TARGET_DIR!
echo Python: !CONDA_PYTHON!
echo.
echo 使用方法: /!SKILL_NAME! [参数]
echo.

pause
