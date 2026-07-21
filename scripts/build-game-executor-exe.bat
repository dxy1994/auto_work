@echo off
chcp 65001 >nul
setlocal

set "PROJECT_ROOT=%~dp0.."
for %%i in ("%PROJECT_ROOT%") do set "PROJECT_ROOT=%%~fi"
set "WORKER_DIR=%PROJECT_ROOT%\worker"
set "VENV_DIR=%PROJECT_ROOT%\.venv-game-executor"
set "PYTHON=%VENV_DIR%\Scripts\python.exe"
set "DIST_DIR=%WORKER_DIR%\dist\game-executor"
set "BUILD_DIR=%WORKER_DIR%\build\game-executor"

echo ========================================
echo   Game Executor Worker 独立打包
echo ========================================

if not exist "%PYTHON%" (
    where python >nul 2>&1 || exit /b 1
    python -m venv "%VENV_DIR%" || exit /b 1
)
"%PYTHON%" -m pip install pyinstaller -r "%WORKER_DIR%\requirements-game-executor.txt" --quiet
if errorlevel 1 exit /b 1

if exist "%DIST_DIR%" rmdir /s /q "%DIST_DIR%"
if exist "%BUILD_DIR%" rmdir /s /q "%BUILD_DIR%"
if exist "%WORKER_DIR%\auto-game-executor.spec" del /q "%WORKER_DIR%\auto-game-executor.spec"

cd /d "%WORKER_DIR%"
"%PYTHON%" -m PyInstaller ^
    --onefile ^
    --console ^
    --name "auto-game-executor" ^
    --distpath "%DIST_DIR%" ^
    --workpath "%BUILD_DIR%" ^
    --specpath "%WORKER_DIR%" ^
    --hidden-import "common" ^
    --hidden-import "game_executor" ^
    --hidden-import "game_executor.executor" ^
    --collect-all "paddle" ^
    --collect-all "paddleocr" ^
    --collect-all "paddlex" ^
    --add-data ".env.game-executor.example;." ^
    --add-data "game_executor\executor\lineage_classic\images;game_executor\executor\lineage_classic\images" ^
    game_executor\main.py
if errorlevel 1 exit /b 1

copy /y "%WORKER_DIR%\.env.game-executor.example" "%DIST_DIR%\.env.game-executor.example" >nul
if exist "%BUILD_DIR%" rmdir /s /q "%BUILD_DIR%"
if exist "%WORKER_DIR%\auto-game-executor.spec" del /q "%WORKER_DIR%\auto-game-executor.spec"
echo [成功] %DIST_DIR%\auto-game-executor.exe
