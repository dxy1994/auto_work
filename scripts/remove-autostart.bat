@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

:: 支持传参指定 EXE 路径
if not "%~1"=="" (
    set "EXE_PATH=%~1"
) else (
    set "PROJECT_ROOT=%~dp0.."
    for %%i in ("!PROJECT_ROOT!") do set "PROJECT_ROOT=%%~fi"
    set "EXE_PATH=!PROJECT_ROOT!\worker\dist\auto-worker.exe"
)

echo ========================================
echo   取消 Worker 开机自启
echo ========================================

echo.

if exist "!EXE_PATH!" (
    "!EXE_PATH!" --uninstall
) else (
    :: EXE 不在则直接删快捷方式
    set "STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
    set "SHORTCUT_PATH=!STARTUP_DIR!\auto-worker.lnk"
    if exist "!SHORTCUT_PATH!" (
        del /q "!SHORTCUT_PATH!"
        echo [完成] 已删除开机自启快捷方式
    ) else (
        echo [提示] 未找到开机自启配置，可能已取消
    )
)

echo.
pause
@echo off
chcp 65001 >nul
setlocal

set "STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "SHORTCUT_PATH=%STARTUP_DIR%\auto-worker.lnk"

echo ========================================
echo   取消 Worker 开机自启
echo ========================================

echo.
if exist "%SHORTCUT_PATH%" (
    del /q "%SHORTCUT_PATH%"
    if exist "%SHORTCUT_PATH%" (
        echo [失败] 无法删除快捷方式，请手动删除:
        echo        %SHORTCUT_PATH%
    ) else (
        echo [完成] 已取消开机自启
    )
) else (
    echo [提示] 未找到开机自启快捷方式，可能已取消
)

echo.
pause

