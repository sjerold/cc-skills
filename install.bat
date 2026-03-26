@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ========================================
echo    Claude Code 插件安装脚本
echo ========================================
echo.

:: 检测当前插件名称（根据目录名判断）
set "CURRENT_DIR=%~dp0"
for %%I in ("%CURRENT_DIR:~0,-1%") do set "PLUGIN_NAME=%%~nxI"
echo 检测到插件: %PLUGIN_NAME%
echo.

:: 设置目标目录
set "TARGET_DIR=%USERPROFILE%\.claude\plugins\%PLUGIN_NAME%"

:: 检查 Python
echo [步骤 1/3] 检查 Python 环境...
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo     × 未找到 Python，请先安装 Python 3.8+
    echo     下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

python --version
echo     √ Python 已安装
echo.

:: 安装依赖
echo [步骤 2/3] 安装 Python 依赖...
if exist "%~dp0requirements.txt" (
    echo     正在安装依赖包...
    pip install -r "%~dp0requirements.txt" -q
    if %errorlevel% neq 0 (
        echo     × 依赖安装失败，尝试使用国内镜像...
        pip install -r "%~dp0requirements.txt" -q -i https://pypi.tuna.tsinghua.edu.cn/simple
    )
    echo     √ 依赖安装完成
) else (
    echo     ! 未找到 requirements.txt，跳过依赖安装
)
echo.

:: 复制插件文件
echo [步骤 3/3] 安装插件文件...
echo     目标目录: %TARGET_DIR%

:: 创建目标目录
if not exist "%TARGET_DIR%" mkdir "%TARGET_DIR%"

:: 复制所有文件
xcopy /e /i /y "%~dp0*" "%TARGET_DIR%\" >nul
if %errorlevel% neq 0 (
    echo     × 文件复制失败
    pause
    exit /b 1
)

:: 删除安装脚本本身（已复制到目标）
del "%TARGET_DIR%\install.bat" 2>nul

echo     √ 插件文件已复制
echo.

:: 完成
echo ========================================
echo    安装完成！
echo ========================================
echo.
echo 插件已安装到: %TARGET_DIR%
echo.
echo 使用方法:
if "%PLUGIN_NAME%"=="baidu-search" (
    echo   /baidu-search 关键词
    echo   /baidu-search 苏州银行 -n 100 -f 10 -s
) else if "%PLUGIN_NAME%"=="file-searcher" (
    echo   /file-searcher 关键词
    echo   /file-searcher 外包 --path C:\Documents
) else (
    echo   /%PLUGIN_NAME% [参数]
)
echo.

pause