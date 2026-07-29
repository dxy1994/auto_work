@echo off
chcp 65001 >nul
setlocal EnableExtensions

powershell.exe -NoProfile -ExecutionPolicy Bypass ^
    -File "%~dp0build-worker-role.ps1" ^
    -Role monitor %*
exit /b %ERRORLEVEL%
