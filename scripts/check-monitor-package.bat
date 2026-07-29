@echo off
chcp 65001 >nul
echo This compatibility entry now uses the shared Worker package checker.
call "%~dp0check-worker-package.bat" %*
exit /b %ERRORLEVEL%
