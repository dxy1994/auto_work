@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

set "PROJECT_ROOT=%~dp0.."
for %%i in ("%PROJECT_ROOT%") do set "PROJECT_ROOT=%%~fi"
set "WORKER_DIR=%PROJECT_ROOT%\worker"
set "VENV_PYTHON=%PROJECT_ROOT%\.venv\Scripts\python.exe"
set "ENV_FILE=%WORKER_DIR%\.env"

echo ========================================
echo   Monitor Worker 启动（监控 + 招呼）
echo ========================================

:: 0. 检查 / 创建 .env
echo.
echo [0/5] 检查配置文件...
if not exist "%ENV_FILE%" (
    echo        未找到 .env，正在从模板创建...
    copy /y "%WORKER_DIR%\.env.monitor.example" "%ENV_FILE%" >nul 2>&1
    if errorlevel 1 (
        echo        [警告] 模板不存在，将使用默认配置
        echo        WORKER_ROLE=monitor > "%ENV_FILE%"
        echo        BACKEND_WS_URL=ws://127.0.0.1:8000/api/agent/ws >> "%ENV_FILE%"
    )
    echo        .env 已创建，请根据需要修改配置后重新运行
    echo        编辑: notepad "%ENV_FILE%"
    pause
    exit /b 0
)
echo        配置文件已就绪

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

:: 2. 安装 Monitor 专用依赖（不含浏览器等 Trader 不需要的包）
echo.
echo [2/5] 安装 Monitor 依赖...
"%VENV_PYTHON%" -m pip install -r "%WORKER_DIR%\requirements-common.txt" --quiet
"%VENV_PYTHON%" -m pip install -r "%WORKER_DIR%\requirements-monitor.txt" --quiet
if errorlevel 1 (
    echo        [警告] 部分依赖安装失败，尝试继续...
)
echo        依赖已就绪

:: 3. 安装 Chromium 浏览器内核（patchright）
echo.
echo [3/5] 安装浏览器内核...
"%VENV_PYTHON%" -m patchright install chromium 2>nul
if errorlevel 1 (
    echo        [提示] 浏览器内核安装失败，将使用系统已安装的 Chrome/Edge
)

:: 4. 检查系统浏览器
echo.
echo [4/5] 检查系统浏览器...
set "BROWSER_FOUND="
for %%p in (
    "%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"
    "C:\Program Files\Google\Chrome\Application\chrome.exe"
    "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
    "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    "C:\Program Files\Microsoft\Edge\Application\msedge.exe"
) do (
    if exist %%p set "BROWSER_FOUND=1"
)
if defined BROWSER_FOUND (
    echo        系统浏览器已就绪
) else (
    echo        [警告] 未检测到 Chrome/Edge，Monitor 需要浏览器！
)

:: 5. 启动
echo.
echo [5/5] 启动 Monitor Worker...
echo.
echo ========================================
echo   角色  : monitor（订单监控 + 招呼发送）
echo   总控  : 见 worker\.env (BACKEND_WS_URL)
echo   按 Ctrl+C 停止
echo ========================================
echo.

cd /d "%WORKER_DIR%"
set WORKER_ROLE=monitor
"%VENV_PYTHON%" main.py
pause
