@echo off
chcp 65001 >nul
setlocal

set "PROJECT_ROOT=%~dp0.."
for %%i in ("%PROJECT_ROOT%") do set "PROJECT_ROOT=%%~fi"
set "WORKER_DIR=%PROJECT_ROOT%\worker"
set "VENV_DIR=%PROJECT_ROOT%\.venv-monitor"
set "PYTHON=%VENV_DIR%\Scripts\python.exe"
set "DIST_DIR=%WORKER_DIR%\dist\monitor"
set "BUILD_DIR=%WORKER_DIR%\build\monitor"

echo ========================================
echo   Monitor Worker 独立打包
echo ========================================

if not exist "%PYTHON%" (
    where python >nul 2>&1 || exit /b 1
    python -m venv "%VENV_DIR%" || exit /b 1
)
"%PYTHON%" -m pip install pyinstaller -r "%WORKER_DIR%\requirements-monitor.txt" --quiet
if errorlevel 1 exit /b 1

if exist "%DIST_DIR%" rmdir /s /q "%DIST_DIR%"
if exist "%BUILD_DIR%" rmdir /s /q "%BUILD_DIR%"
if exist "%WORKER_DIR%\auto-monitor.spec" del /q "%WORKER_DIR%\auto-monitor.spec"

cd /d "%WORKER_DIR%"
"%PYTHON%" -m PyInstaller ^
    --onefile ^
    --console ^
    --name "auto-monitor" ^
    --distpath "%DIST_DIR%" ^
    --workpath "%BUILD_DIR%" ^
    --specpath "%WORKER_DIR%" ^
    --hidden-import "common" ^
    --hidden-import "monitor" ^
    --hidden-import "monitor.browser" ^
    --hidden-import "monitor.chat" ^
    --hidden-import "monitor.monitoring" ^
    --hidden-import "monitor.orders" ^
    --collect-all "patchright" ^
    --add-data ".env.monitor.example;." ^
    monitor\main.py
if errorlevel 1 exit /b 1

copy /y "%WORKER_DIR%\.env.monitor.example" "%DIST_DIR%\.env.monitor.example" >nul
if exist "%BUILD_DIR%" rmdir /s /q "%BUILD_DIR%"
if exist "%WORKER_DIR%\auto-monitor.spec" del /q "%WORKER_DIR%\auto-monitor.spec"
echo [成功] %DIST_DIR%\auto-monitor.exe
