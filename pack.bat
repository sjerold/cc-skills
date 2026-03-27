@echo off
chcp 65001 >/dev/null
setlocal enabledelayedexpansion

echo ========================================
echo    Claude Code Skills 打包工具
echo ========================================
echo.

set "SCRIPT_DIR=%~dp0"
set "OUTPUT_DIR=%SCRIPT_DIR%dist"

if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%"

echo 正在打包 Skills...
echo.

for /d %%d in ("%SCRIPT_DIR%skills\*") do (
    set "SKILL_NAME=%%~nd"
    echo [打包] !SKILL_NAME!

    if exist "%SCRIPT_DIR%temp_pack" rmdir /s /q "%SCRIPT_DIR%temp_pack"
    mkdir "%SCRIPT_DIR%temp_pack\!SKILL_NAME!"

    :: 复制 skill 文件
    xcopy /e /i /q "%%d\*" "%SCRIPT_DIR%temp_pack\!SKILL_NAME!\" >/dev/null

    :: 复制安装脚本
    copy /y "%SCRIPT_DIR%install.bat" "%SCRIPT_DIR%temp_pack\!SKILL_NAME!\" >/dev/null

    :: 确保包含 environment.yml
    if exist "%%d\environment.yml" (
        echo     √ 包含 environment.yml
    ) else (
        echo     ! 缺少 environment.yml
    )

    :: 打包
    cd /d "%SCRIPT_DIR%temp_pack"
    powershell -command "Compress-Archive -Path '!SKILL_NAME!' -DestinationPath '..\dist\!SKILL_NAME!.zip' -Force"

    cd /d "%SCRIPT_DIR%"
    rmdir /s /q "%SCRIPT_DIR%temp_pack"

    echo     √ dist\!SKILL_NAME!.zip
)

echo.
echo ========================================
echo 打包完成！输出目录: %OUTPUT_DIR%
echo ========================================

dir /b "%OUTPUT_DIR%\*.zip"
pause
