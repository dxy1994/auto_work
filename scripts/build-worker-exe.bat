@echo off
chcp 65001 >nul
echo ========================================
echo   构建两个独立 Worker 安装包
echo ========================================
call "%~dp0build-monitor-exe.bat"
if errorlevel 1 exit /b 1
call "%~dp0build-game-executor-exe.bat"
if errorlevel 1 exit /b 1
echo.
echo 构建完成。请将两个 EXE 分别部署到不同主机。
