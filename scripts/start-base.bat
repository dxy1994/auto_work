@echo off
chcp 65001 >nul
cd /d "%~dp0.."

echo ========================================
echo   启动基础环境 (MySQL + RustFS)
echo ========================================

echo.
echo 正在启动 MySQL 和 RustFS...
docker compose up -d mysql rustfs

REM ── 等待 MySQL 就绪 ──
echo.
echo 等待 MySQL 就绪...
:wait_mysql
docker compose exec -T mysql mysqladmin ping -h localhost -u root -proot --silent >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    <nul set /p =.
    timeout /t 3 /nobreak >nul
    goto wait_mysql
)
echo  MySQL 已就绪 ✓

REM ── 等待 RustFS 就绪 ──
echo.
echo 等待 RustFS 就绪...
:wait_rustfs
curl -sf http://127.0.0.1:9000/ >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    <nul set /p =.
    timeout /t 3 /nobreak >nul
    goto wait_rustfs
)
echo  RustFS 已就绪 ✓

echo.
echo ========================================
echo   基础环境已就绪
echo   MySQL  : 127.0.0.1:3306  (root/root)
echo   RustFS : 127.0.0.1:9000
echo ========================================
