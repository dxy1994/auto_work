@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

set "PROJECT_ROOT=%~dp0.."
for %%i in ("%PROJECT_ROOT%") do set "PROJECT_ROOT=%%~fi"
set "WORKER_DIR=%PROJECT_ROOT%\worker"
echo ========================================
echo   统一 Worker 启动入口已停用
echo ========================================
echo.
echo   Monitor（监控 + 招呼）: scripts\start-monitor.bat
echo   Game Executor（游戏执行）: scripts\start-game-executor.bat
echo.
echo   两种角色应部署在不同主机，请运行对应脚本。
echo ========================================
pause
exit /b 2
