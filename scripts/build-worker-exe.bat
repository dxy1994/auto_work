@echo off
chcp 65001 >nul
setlocal EnableExtensions

echo ============================================================
echo   Build both independent Worker deployment packages
echo ============================================================

call "%~dp0build-monitor-exe.bat" %*
if errorlevel 1 exit /b %ERRORLEVEL%

call "%~dp0build-game-executor-exe.bat" %*
if errorlevel 1 exit /b %ERRORLEVEL%

echo.
echo [SUCCESS] Both role packages are ready under worker\dist.
echo           Deploy them to separate machines.
exit /b 0
