@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

set "PROJECT_ROOT=%~dp0.."
for %%i in ("%PROJECT_ROOT%") do set "PROJECT_ROOT=%%~fi"

:: 支持传参指定 EXE 路径：setup-autostart.bat "D:\path\to\auto-worker.exe"
if not "%~1"=="" (
    set "EXE_PATH=%~1"
) else (
    set "EXE_PATH=%PROJECT_ROOT%\auto-worker.exe"
)

echo ========================================
echo   Worker 开机自启配置
echo ========================================

:: 查找 EXE
echo.
echo [1/2] 查找 auto-worker.exe...
if exist "!EXE_PATH!" (
    echo        !EXE_PATH!
    echo        已找到 ✓
) else (
    echo        [错误] 未找到 !EXE_PATH!
    echo.
    echo        用法 1: 将本脚本放在项目的 scripts\ 目录下运行
    echo        用法 2: setup-autostart.bat "D:\path\to\auto-worker.exe"
    echo        用法 3: 直接在目标机器上运行 auto-worker.exe --install
    pause
    exit /b 1
)

:: 委托给 EXE 自身处理
echo.
echo [2/2] 配置开机自启...
"!EXE_PATH!" --install

if errorlevel 1 (
    echo.
    echo [失败] 自启配置未成功
    pause
    exit /b 1
)

echo.
echo ========================================
echo   [完成] 下次开机自动启动 Worker
echo   取消: auto-worker.exe --uninstall
echo ========================================

pause
