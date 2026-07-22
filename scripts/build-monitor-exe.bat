@echo off
chcp 65001 >nul
setlocal EnableExtensions EnableDelayedExpansion

for %%I in ("%~dp0..") do set "PROJECT_ROOT=%%~fI"
set "WORKER_DIR=%PROJECT_ROOT%\worker"
set "VENV_DIR=%PROJECT_ROOT%\.venv-monitor"
set "VENV_PYTHON=%VENV_DIR%\Scripts\python.exe"
set "DIST_DIR=%WORKER_DIR%\dist\monitor"
set "BUILD_DIR=%WORKER_DIR%\build\monitor"
set "BOOTSTRAP_PYTHON="
set "BOOTSTRAP_ARGS="

echo ========================================
echo   Monitor Worker EXE build
echo ========================================

if exist "%VENV_PYTHON%" (
    "%VENV_PYTHON%" -c "import sys" >nul 2>&1
    if errorlevel 1 (
        echo [WARN] Existing build environment is invalid; recreating it.
        rmdir /s /q "%VENV_DIR%"
    )
)

if not exist "%VENV_PYTHON%" (
    call :find_bootstrap_python
    if not defined BOOTSTRAP_PYTHON (
        echo [ERROR] No usable Python 3 installation was found.
        echo [ERROR] Install Python 3.10+ or set PYTHON_EXE to python.exe and retry.
        exit /b 1
    )

    echo [1/3] Creating build environment with "!BOOTSTRAP_PYTHON!" !BOOTSTRAP_ARGS!
    "!BOOTSTRAP_PYTHON!" !BOOTSTRAP_ARGS! -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo [ERROR] Failed to create "%VENV_DIR%".
        exit /b 1
    )
)

echo [2/3] Installing monitor dependencies...
"%VENV_PYTHON%" -m pip install --disable-pip-version-check pyinstaller -r "%WORKER_DIR%\requirements-monitor.txt"
if errorlevel 1 (
    echo [ERROR] Dependency installation failed.
    exit /b 1
)

if not exist "%DIST_DIR%" mkdir "%DIST_DIR%"
if exist "%DIST_DIR%\auto-monitor.exe" del /q "%DIST_DIR%\auto-monitor.exe"
if exist "%BUILD_DIR%" rmdir /s /q "%BUILD_DIR%"
if exist "%WORKER_DIR%\auto-monitor.spec" del /q "%WORKER_DIR%\auto-monitor.spec"

echo [3/3] Building auto-monitor.exe...
cd /d "%WORKER_DIR%"
"%VENV_PYTHON%" -m PyInstaller ^
    --onefile ^
    --console ^
    --clean ^
    --noconfirm ^
    --name "auto-monitor" ^
    --distpath "%DIST_DIR%" ^
    --workpath "%BUILD_DIR%" ^
    --specpath "%WORKER_DIR%" ^
    --collect-submodules "common" ^
    --collect-submodules "monitor" ^
    --collect-all "patchright" ^
    --add-data ".env.monitor.example;." ^
    monitor\main.py
if errorlevel 1 (
    echo [ERROR] PyInstaller build failed.
    exit /b 1
)

copy /y "%WORKER_DIR%\.env.monitor.example" "%DIST_DIR%\.env.monitor.example" >nul
if exist "%WORKER_DIR%\.env" (
    copy /y "%WORKER_DIR%\.env" "%DIST_DIR%\.env" >nul
) else if not exist "%DIST_DIR%\.env" (
    copy /y "%WORKER_DIR%\.env.monitor.example" "%DIST_DIR%\.env" >nul
)
if exist "%BUILD_DIR%" rmdir /s /q "%BUILD_DIR%"
if exist "%WORKER_DIR%\auto-monitor.spec" del /q "%WORKER_DIR%\auto-monitor.spec"

echo [SUCCESS] %DIST_DIR%\auto-monitor.exe
exit /b 0

:find_bootstrap_python
if defined PYTHON_EXE call :try_python "%PYTHON_EXE%"
if defined BOOTSTRAP_PYTHON exit /b 0

for /f "delims=" %%P in ('where python.exe 2^>nul') do call :try_python "%%P"
if defined BOOTSTRAP_PYTHON exit /b 0

for /f "delims=" %%P in ('where py.exe 2^>nul') do call :try_py "%%P"
if defined BOOTSTRAP_PYTHON exit /b 0

call :try_python "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
call :try_python "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
call :try_python "%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
call :try_python "%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
exit /b 0

:try_python
if defined BOOTSTRAP_PYTHON exit /b 0
if "%~1"=="" exit /b 0
if not exist "%~1" exit /b 0
"%~1" -c "import sys, venv" >nul 2>&1
if errorlevel 1 exit /b 0
set "BOOTSTRAP_PYTHON=%~1"
set "BOOTSTRAP_ARGS="
exit /b 0

:try_py
if defined BOOTSTRAP_PYTHON exit /b 0
if "%~1"=="" exit /b 0
if not exist "%~1" exit /b 0
"%~1" -3 -c "import sys, venv" >nul 2>&1
if errorlevel 1 exit /b 0
set "BOOTSTRAP_PYTHON=%~1"
set "BOOTSTRAP_ARGS=-3"
exit /b 0
