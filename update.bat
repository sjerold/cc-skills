@echo off
chcp 65001 >/dev/null
setlocal enabledelayedexpansion

echo ========================================
echo    Claude Code Skill 更新脚本
echo ========================================
echo.

set "PLUGIN_DIR=%USERPROFILE%\.claude\plugins"

:: 列出已安装的插件
echo 已安装的插件:
echo.
set /a count=0
for /d %%d in ("%PLUGIN_DIR%\*") do (
    if exist "%%d\.claude-plugin\plugin.json" (
        set /a count+=1
        for /f "tokens=2 delims=:" %%a in ('findstr "name" "%%d\.claude-plugin\plugin.json" 2^>nul') do (
            set "pname=%%a"
            set "pname=!pname:"=!"
            set "pname=!pname:,=!"
            set "pname=!pname: =!"
            echo   !count!. !pname!
        )
    )
)

if !count! equ 0 (
    echo   (无已安装的插件)
    pause
    exit /b 0
)

echo.
set /p choice="请输入要更新的插件编号 (或输入 all 更新全部): "

if /i "!choice!"=="all" (
    echo.
    echo 正在更新所有插件...
    for /d %%d in ("%PLUGIN_DIR%\*") do (
        if exist "%%d\.claude-plugin\plugin.json" (
            echo.
            echo [更新] %%~nd
            call :update_plugin "%%d" "%%~nd"
        )
    )
) else (
    set /a idx=0
    for /d %%d in ("%PLUGIN_DIR%\*") do (
        if exist "%%d\.claude-plugin\plugin.json" (
            set /a idx+=1
            if !idx! equ !choice! (
                echo.
                echo [更新] %%~nd
                call :update_plugin "%%d" "%%~nd"
            )
        )
    )
)

echo.
echo ========================================
echo    更新完成！
echo ========================================
pause
exit /b 0

:update_plugin
set "TARGET_DIR=%~1"
set "NAME=%~2"

:: 检查是否有 .python_path 文件
if exist "%TARGET_DIR%\.python_path" (
    set /p CONDA_PYTHON=<"%TARGET_DIR%\.python_path"
    echo     Python: !CONDA_PYTHON!
)

:: 更新依赖
if exist "%TARGET_DIR%\requirements.txt" (
    echo     正在更新依赖...
    if defined CONDA_PYTHON (
        "!CONDA_PYTHON!" -m pip install -r "%TARGET_DIR%\requirements.txt" -q --upgrade
    ) else (
        pip install -r "%TARGET_DIR%\requirements.txt" -q --upgrade
    )
    echo     √ 依赖已更新
)

:: 更新 environment.yml
if exist "%TARGET_DIR%\environment.yml" (
    echo     正在更新 Conda 环境...
    conda env update -n dsbot_env -f "%TARGET_DIR%\environment.yml" --prune
    echo     √ 环境已更新
)

echo     √ 插件更新完成
exit /b 0
