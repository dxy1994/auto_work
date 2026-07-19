@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

:: 解析 --autostart 参数
set "AUTO_START=0"
:parse_args
if "%~1"=="" goto :args_done
if /i "%~1"=="--autostart" set "AUTO_START=1"
if /i "%~1"=="-a" set "AUTO_START=1"
shift
goto :parse_args
:args_done

set "PROJECT_ROOT=%~dp0.."
for %%i in ("%PROJECT_ROOT%") do set "PROJECT_ROOT=%%~fi"
set "WORKER_DIR=%PROJECT_ROOT%\worker"
set "VENV_PYTHON=%PROJECT_ROOT%\.venv\Scripts\python.exe"
set "DIST_DIR=%WORKER_DIR%\dist"
set "BUILD_DIR=%WORKER_DIR%\build"
set "EXE_PATH=%DIST_DIR%\auto-worker.exe"

echo ========================================
echo   Worker EXE 打包（PyInstaller）
if "%AUTO_START%"=="1" echo   ^(含开机自启配置^)
echo ========================================

:: 1. 检查虚拟环境
echo.
echo [1/5] 检查 Python 虚拟环境...
if not exist "%VENV_PYTHON%" (
    echo        [错误] 虚拟环境不存在，请先运行 start-worker.bat
    pause
    exit /b 1
)
echo        虚拟环境已就绪

:: 2. 安装 PyInstaller
echo.
echo [2/5] 安装 PyInstaller...
"%VENV_PYTHON%" -m pip install pyinstaller --quiet 2>nul
if errorlevel 1 (
    echo        [错误] PyInstaller 安装失败
    pause
    exit /b 1
)
echo        PyInstaller 已就绪

:: 3. 安装项目依赖（确保 PyInstaller 能找到）
echo.
echo [3/5] 检查项目依赖...
"%VENV_PYTHON%" -m pip install -r "%WORKER_DIR%\requirements.txt" --quiet 2>nul
echo        依赖已就绪

:: 4. 清理旧构建
echo.
echo [4/5] 清理旧构建文件...
if exist "%DIST_DIR%" rmdir /s /q "%DIST_DIR%"
if exist "%BUILD_DIR%" rmdir /s /q "%BUILD_DIR%"
if exist "%WORKER_DIR%\auto-worker.spec" del /q "%WORKER_DIR%\auto-worker.spec"
echo        清理完成

:: 5. 执行 PyInstaller 打包
echo.
echo [5/5] 开始打包...
echo.
echo ========================================
echo   打包参数:
echo     - 单文件模式
echo     - 输出目录: worker\dist
echo     - 入口文件: worker\main.py
echo ========================================
echo.

cd /d "%WORKER_DIR%"

"%VENV_PYTHON%" -m PyInstaller ^
    --onefile ^
    --console ^
    --name "auto-worker" ^
    --distpath "%DIST_DIR%" ^
    --workpath "%BUILD_DIR%" ^
    --specpath "%WORKER_DIR%" ^
    --hidden-import "patchright" ^
    --hidden-import "patchright.async_api" ^
    --hidden-import "shared" ^
    --hidden-import "monitor" ^
    --hidden-import "monitor.browser" ^
    --hidden-import "monitor.chat" ^
    --hidden-import "monitor.monitoring" ^
    --hidden-import "monitor.orders" ^
    --hidden-import "trader" ^
    --hidden-import "trader.executor" ^
    --hidden-import "websockets" ^
    --hidden-import "dotenv" ^
    --collect-all "patchright" ^
    --add-data ".env.monitor.example;." ^
    --add-data ".env.trader.example;." ^
    main.py

if errorlevel 1 (
    echo.
    echo ========================================
    echo   [失败] 打包出错，请检查上方日志
    echo ========================================
    pause
    exit /b 1
)

echo.
echo ========================================
echo   [成功] 打包完成！
echo.
echo   输出文件: worker\dist\auto-worker.exe
echo.
echo   使用说明:
echo     1. 根据角色复制对应模板:
echo        Monitor: copy .env.monitor.example .env
echo        Trader:  copy .env.trader.example .env
echo     2. 编辑 .env，修改 BACKEND_WS_URL 为总控地址
echo     3. Monitor 需确保已安装 Chrome/Edge
echo     4. 双击 auto-worker.exe 启动
echo.
echo   注意: EXE 启动较慢（解压依赖），请耐心等候
echo ========================================

:: 清理 build 临时文件
echo.
echo 清理临时构建文件...
if exist "%BUILD_DIR%" rmdir /s /q "%BUILD_DIR%"
if exist "%WORKER_DIR%\auto-worker.spec" del /q "%WORKER_DIR%\auto-worker.spec"
echo 清理完成

:: ── 开机自启 ──
if "%AUTO_START%"=="1" (
    echo.
    echo ========================================
    echo   配置开机自启（auto-worker.exe --install）...
    echo ========================================

    if exist "%EXE_PATH%" (
        "%EXE_PATH%" --install
        if errorlevel 1 (
            echo   [警告] 开机自启配置失败，可部署后手动执行: auto-worker.exe --install
        )
    ) else (
        echo   [警告] 未找到 EXE，跳过开机自启
    )

    echo ========================================
)

pause
