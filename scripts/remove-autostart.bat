@echo off
chcp 65001 >nul
if "%~1"=="" (
    echo 用法: remove-autostart.bat "D:\path\to\auto-monitor.exe"
    echo   或: remove-autostart.bat "D:\path\to\auto-game-executor.exe"
    exit /b 2
)
if not exist "%~1" (
    echo [错误] 未找到 EXE: %~1
    exit /b 1
)
"%~1" --uninstall
