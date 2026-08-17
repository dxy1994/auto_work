@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

set "PROJECT_ROOT=%~dp0.."
for %%i in ("%PROJECT_ROOT%") do set "PROJECT_ROOT=%%~fi"
set "WORKER_DIR=%PROJECT_ROOT%\worker"
set "VENV_PYTHON=%PROJECT_ROOT%\.venv-game-executor\Scripts\python.exe"
set "ENV_FILE=%WORKER_DIR%\.env"

echo ========================================
echo   Game Executor Worker 启动（游戏交易执行）
echo ========================================

:: 0. 检查 / 创建 .env
echo.
echo [0/3] 检查配置文件...
if not exist "%ENV_FILE%" (
    echo        未找到 .env，正在从模板创建...
    copy /y "%WORKER_DIR%\.env.game-executor.example" "%ENV_FILE%" >nul 2>&1
    if errorlevel 1 (
        echo        [警告] 模板不存在，将使用默认配置
        echo        BACKEND_WS_URL=ws://127.0.0.1:8000/api/agent/ws > "%ENV_FILE%"
    )
    echo        .env 已创建，请修改 BACKEND_WS_URL 后重新运行
    echo        编辑: notepad "%ENV_FILE%"
    pause
    exit /b 0
)
echo        配置文件已就绪

:: 1. 检查虚拟环境 + 安装游戏执行端独立依赖
echo.
echo [1/3] 检查环境 / 安装依赖...
if not exist "%VENV_PYTHON%" (
    echo        虚拟环境不存在，正在创建...
    where python >nul 2>&1 || (
        echo        [错误] 未找到 Python，请先安装 Python 3.10+
        pause
        exit /b 1
    )
    python -m venv "%PROJECT_ROOT%\.venv-game-executor"
    echo        虚拟环境已创建
)
"%VENV_PYTHON%" -m pip install -r "%WORKER_DIR%\requirements-game-executor.txt" --quiet
echo        依赖已就绪

:: 2. 检查 ESP32C3 硬件（可选）
echo.
echo [2/3] 检查 ESP32C3 硬件...
echo        （固件就绪后通过串口 / HTTP 自动检测）
echo        跳过硬件检查

:: 3. 启动
echo.
echo [3/3] 启动 Game Executor Worker...
echo.
echo ========================================
echo   角色  : game_executor（游戏交易执行）
echo   硬件  : ESP32C3 + CH9329 键鼠
echo   总控  : 见 worker\.env (BACKEND_WS_URL)
echo   按 Ctrl+C 停止
echo ========================================
echo.

cd /d "%WORKER_DIR%"
"%VENV_PYTHON%" -m game_executor.main
pause
