@echo off
chcp 65001 >nul
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

set "MONITOR_EXE=%~dp0auto-monitor.exe"
set "HASH_FILE=%~dp0auto-monitor.exe.sha256"

echo ========================================
echo   Auto Monitor compatibility check
echo ========================================
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
    "Write-Host ('Windows: ' + [Environment]::OSVersion.VersionString);" ^
    "Write-Host ('OS architecture: ' + [Runtime.InteropServices.RuntimeInformation]::OSArchitecture);" ^
    "Write-Host ('CPU architecture: ' + $env:PROCESSOR_ARCHITECTURE)"

if not exist "%MONITOR_EXE%" (
    echo [ERROR] auto-monitor.exe is missing from this directory.
    pause
    exit /b 1
)

for /f "usebackq delims=" %%H in (`powershell.exe -NoProfile -Command "(Get-FileHash -LiteralPath '%MONITOR_EXE%' -Algorithm SHA256).Hash"`) do set "ACTUAL_HASH=%%H"
echo EXE SHA256: !ACTUAL_HASH!

if exist "%HASH_FILE%" (
    set /p EXPECTED_HASH=<"%HASH_FILE%"
    echo Expected:   !EXPECTED_HASH!
    if /i not "!ACTUAL_HASH!"=="!EXPECTED_HASH!" (
        echo [ERROR] The EXE was damaged or changed during transfer.
        echo [ERROR] Copy and extract auto-monitor-windows-x64.zip again.
        pause
        exit /b 2
    )
    echo [OK] File integrity check passed.
) else (
    echo [WARN] SHA256 file is missing; file integrity cannot be verified.
)

echo Removing the downloaded-file block flag...
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
    "Unblock-File -LiteralPath '%MONITOR_EXE%';" ^
    "$signature = Get-AuthenticodeSignature -LiteralPath '%MONITOR_EXE%';" ^
    "Write-Host ('Signature status: ' + $signature.Status)"

echo.
echo Starting auto-monitor.exe...
start "" "%MONITOR_EXE%"
timeout /t 5 /nobreak >nul

powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
    "if (Get-Process -Name 'auto-monitor' -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }"
if errorlevel 1 (
    echo [ERROR] auto-monitor.exe did not remain running.
    echo Check Windows Security - Protection history and send this window to the developer.
    pause
    exit /b 3
)

echo [OK] auto-monitor.exe is running.
pause
exit /b 0
