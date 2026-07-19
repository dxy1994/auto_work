@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

set "PROJECT_ROOT=%~dp0.."
for %%i in ("%PROJECT_ROOT%") do set "PROJECT_ROOT=%%~fi"
set "WORKER_DIR=%PROJECT_ROOT%\worker"
set "VENV_PYTHON=%PROJECT_ROOT%\.venv\Scripts\python.exe"
set "ENV_FILE=%WORKER_DIR%\.env"
set "ENV_EXAMPLE=%WORKER_DIR%\.env.example"

echo ========================================
echo   Worker 启动 — 请按角色选择启动脚本
echo ========================================
echo.
echo   Monitor（监控 + 招呼）: scripts\start-monitor.bat
echo   Trader（游戏交易执行）: scripts\start-trader.bat
echo.
echo   本脚本保留兼容旧习惯，默认启动 Monitor
echo ========================================

:: 0. 检查 .env 配置文件
echo.
echo [0/5] 检查配置文件...
if not exist "%ENV_FILE%" (
    if exist "%ENV_EXAMPLE%" (
        echo        未找到 .env，正在从 .env.example 复制...
        copy /y "%ENV_EXAMPLE%" "%ENV_FILE%" >nul
        echo        .env 已创建，请根据需要修改 BACKEND_WS_URL
    ) else (
        echo        [警告] 未找到 .env.example，将使用默认配置
    )
) else (
    echo        配置文件已就绪
)

:: 1. 检查虚拟环境
echo.
echo [1/5] 检查 Python 虚拟环境...
if not exist "%VENV_PYTHON%" (
    echo        虚拟环境不存在，正在创建...
    where python >nul 2>&1 || (
        echo        [错误] 未找到 Python，请先安装 Python 3.10+
        pause
        exit /b 1
    )
    python -m venv "%PROJECT_ROOT%\.venv"
    if errorlevel 1 (
        echo        [错误] 虚拟环境创建失败
        pause
        exit /b 1
    )
    echo        虚拟环境已创建
) else (
    echo        虚拟环境已就绪
)

:: 2. 检查并安装依赖
echo.
echo [2/5] 检查 Python 依赖...
"%VENV_PYTHON%" -m pip install -r "%WORKER_DIR%\requirements.txt" --quiet
if errorlevel 1 (
    echo        [警告] 部分依赖安装失败，尝试继续...
)
echo        依赖已就绪

:: 3. 安装 Chromium 浏览器（patchright）
echo.
echo [3/5] 检查浏览器内核...
"%VENV_PYTHON%" -m patchright install chromium 2>nul
if errorlevel 1 (
    echo        [提示] 浏览器内核安装失败，将使用系统已安装的 Chrome/Edge
)

:: 4. 检查 Chrome/Edge 是否可用
echo.
echo [4/5] 检查系统浏览器...
set "CHROME_FOUND="
for %%p in (
    "%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"
    "C:\Program Files\Google\Chrome\Application\chrome.exe"
    "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
    "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    "C:\Program Files\Microsoft\Edge\Application\msedge.exe"
) do (
    if exist %%p (
        set "CHROME_FOUND=1"
    )
)
if defined CHROME_FOUND (
    echo        系统浏览器已就绪
) else (
    echo        [警告] 未检测到 Chrome/Edge，请确保浏览器已安装
)

:: 5. 启动 worker
echo.
echo [5/5] 启动 Worker...
echo.
echo ========================================
echo   连接总控: 见 worker\.env (BACKEND_WS_URL)
echo   提示: 编辑 worker\.env 修改总控地址
echo   按 Ctrl+C 停止 Worker
echo ========================================
echo.

cd /d "%WORKER_DIR%"
"%VENV_PYTHON%" main.py
pause
