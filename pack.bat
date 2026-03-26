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

for /d %%d in ("%SCRIPT_DIR%skills\*") do (
    set "SKILL_NAME=%%~nd"
    echo [打包] !SKILL_NAME!

    if exist "%SCRIPT_DIR%temp_pack" rmdir /s /q "%SCRIPT_DIR%temp_pack"
    mkdir "%SCRIPT_DIR%temp_pack\!SKILL_NAME!"

    xcopy /e /i /q "%%d\*" "%SCRIPT_DIR%temp_pack\!SKILL_NAME!\" >/dev/null
    copy /y "%SCRIPT_DIR%install.bat" "%SCRIPT_DIR%temp_pack\!SKILL_NAME!\" >/dev/null

    cd /d "%SCRIPT_DIR%temp_pack"
    powershell -command "Compress-Archive -Path '!SKILL_NAME!' -DestinationPath '..\dist\!SKILL_NAME!.zip' -Force"

    cd /d "%SCRIPT_DIR%"
    rmdir /s /q "%SCRIPT_DIR%temp_pack"

    echo     √ dist\!SKILL_NAME!.zip
)

echo.
echo 打包完成！输出目录: %OUTPUT_DIR%
dir /b "%OUTPUT_DIR%\*.zip"
pause
