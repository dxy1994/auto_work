@echo off
chcp 65001 >nul
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

set "CHECK_ONLY="
if /i "%~1"=="--check-only" set "CHECK_ONLY=1"

if exist "%~dp0auto-monitor.exe" (
    set "APP_EXE=auto-monitor.exe"
    set "PROCESS_NAME=auto-monitor"
    set "APP_ROLE=Monitor Worker"
) else if exist "%~dp0auto-game-executor.exe" (
    set "APP_EXE=auto-game-executor.exe"
    set "PROCESS_NAME=auto-game-executor"
    set "APP_ROLE=Game Executor Worker"
) else (
    echo [ERROR] No supported Worker executable was found in:
    echo         %~dp0
    pause
    exit /b 1
)

set "APP_PATH=%~dp0!APP_EXE!"
set "HASH_FILE=%~dp0!APP_EXE!.sha256"

echo ============================================================
echo   !APP_ROLE! package check
echo ============================================================
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
    "Write-Host ('Windows: ' + [Environment]::OSVersion.VersionString);" ^
    "Write-Host ('OS architecture: ' + [Runtime.InteropServices.RuntimeInformation]::OSArchitecture);" ^
    "Write-Host ('CPU architecture: ' + $env:PROCESSOR_ARCHITECTURE)"

if /i not "%PROCESSOR_ARCHITECTURE%"=="AMD64" (
    echo [ERROR] This package requires 64-bit Windows on x64 hardware.
    pause
    exit /b 2
)

for /f "usebackq delims=" %%H in (`powershell.exe -NoProfile -Command "(Get-FileHash -LiteralPath '!APP_PATH!' -Algorithm SHA256).Hash"`) do set "ACTUAL_HASH=%%H"
echo EXE SHA256: !ACTUAL_HASH!

if exist "!HASH_FILE!" (
    set /p EXPECTED_HASH=<"!HASH_FILE!"
    echo Expected:   !EXPECTED_HASH!
    if /i not "!ACTUAL_HASH!"=="!EXPECTED_HASH!" (
        echo [ERROR] The executable was damaged or changed during transfer.
        echo [ERROR] Extract the deployment ZIP again.
        pause
        exit /b 3
    )
    echo [OK] File integrity check passed.
) else (
    echo [WARN] SHA256 file is missing; integrity cannot be verified.
)

if not exist "%~dp0.env" (
    if exist "%~dp0.env.example" (
        copy /y "%~dp0.env.example" "%~dp0.env" >nul
        echo [WARN] .env was created from the template. Edit it before production use.
    ) else (
        echo [ERROR] Both .env and .env.example are missing.
        pause
        exit /b 4
    )
)

echo Removing the downloaded-file block flag...
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
    "Unblock-File -LiteralPath '!APP_PATH!';" ^
    "$signature = Get-AuthenticodeSignature -LiteralPath '!APP_PATH!';" ^
    "Write-Host ('Signature status: ' + $signature.Status)"

echo.
echo Running packaged dependency and asset self-check...
"!APP_PATH!" --self-check
if errorlevel 1 (
    echo [ERROR] Package self-check failed. Do not deploy this build.
    pause
    exit /b 5
)
echo [OK] Package self-check passed.

if defined CHECK_ONLY (
    echo [OK] Check-only mode completed.
    pause
    exit /b 0
)

echo.
echo Starting !APP_EXE!...
start "" "!APP_PATH!"
timeout /t 5 /nobreak >nul

powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
    "if (Get-Process -Name '!PROCESS_NAME!' -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }"
if errorlevel 1 (
    echo [ERROR] !APP_EXE! did not remain running.
    echo Review this console and Windows Security - Protection history.
    pause
    exit /b 6
)

echo [OK] !APP_EXE! is running.
pause
exit /b 0
