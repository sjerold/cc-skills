@echo off
chcp 65001 >/dev/null
setlocal enabledelayedexpansion

echo ========================================
echo    Claude Code Skill 安装脚本
echo ========================================
echo.

set "SCRIPT_DIR=%~dp0"
set "SKILL_NAME="
set "SKILL_DIR="

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

set "TARGET_DIR=%USERPROFILE%\.claude\plugins\!SKILL_NAME!"

echo [步骤 1/3] 检查 Python 环境...
where python >/dev/null 2>&1
if %errorlevel% neq 0 (
    echo     × 未找到 Python，请先安装 Python 3.8+
    pause
    exit /b 1
)
python --version
echo     √ Python 已安装
echo.

echo [步骤 2/3] 安装 Python 依赖...
if exist "!SKILL_DIR!\requirements.txt" (
    pip install -r "!SKILL_DIR!\requirements.txt" -q
    if %errorlevel% neq 0 (
        pip install -r "!SKILL_DIR!\requirements.txt" -q -i https://pypi.tuna.tsinghua.edu.cn/simple
    )
    echo     √ 依赖安装完成
)
echo.

echo [步骤 3/3] 安装插件文件...
if not exist "!TARGET_DIR!" mkdir "!TARGET_DIR!"
xcopy /e /i /y "!SKILL_DIR!\*" "!TARGET_DIR!\" >/dev/null
echo     √ 插件文件已复制
echo.

echo ========================================
echo    安装完成！
echo ========================================
echo.
echo 使用方法: /!SKILL_NAME! [参数]
pause
