@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ========================================
echo    Claude Code 插件打包工具
echo ========================================
echo.

:: 设置变量
set "PLUGIN_DIR=%~dp0"
set "OUTPUT_DIR=%PLUGIN_DIR%dist"
set "DATE_STR=%date:~0,4%%date:~5,2%%date:~8,2%"

:: 创建输出目录
if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%"

:: 打包 baidu-search
echo [1/2] 打包 baidu-search...
cd /d "%PLUGIN_DIR%"
if exist "baidu-search" (
    :: 创建临时目录
    if exist "temp_pack" rmdir /s /q temp_pack
    mkdir temp_pack\baidu-search

    :: 复制文件
    xcopy /e /i /q "baidu-search\*" "temp_pack\baidu-search\"

    :: 复制安装脚本
    copy /y "install.bat" "temp_pack\baidu-search\"
    copy /y "requirements.txt" "temp_pack\baidu-search\"

    :: 打包
    cd temp_pack
    powershell -command "Compress-Archive -Path 'baidu-search' -DestinationPath '..\dist\baidu-search-plugin.zip' -Force"
    cd ..

    :: 清理
    rmdir /s /q temp_pack
    echo     √ baidu-search-plugin.zip 已创建
) else (
    echo     × baidu-search 目录不存在
)

:: 打包 file-searcher
echo [2/2] 打包 file-searcher...
if exist "file-searcher" (
    if exist "temp_pack" rmdir /s /q temp_pack
    mkdir temp_pack\file-searcher

    xcopy /e /i /q "file-searcher\*" "temp_pack\file-searcher\"
    copy /y "install.bat" "temp_pack\file-searcher\"
    copy /y "requirements-file-searcher.txt" "temp_pack\file-searcher\requirements.txt"

    cd temp_pack
    powershell -command "Compress-Archive -Path 'file-searcher' -DestinationPath '..\dist\file-searcher-plugin.zip' -Force"
    cd ..

    rmdir /s /q temp_pack
    echo     √ file-searcher-plugin.zip 已创建
) else (
    echo     × file-searcher 目录不存在
)

echo.
echo ========================================
echo 打包完成！输出目录: %OUTPUT_DIR%
echo ========================================
echo.

:: 列出生成的文件
dir /b "%OUTPUT_DIR%\*.zip"

pause