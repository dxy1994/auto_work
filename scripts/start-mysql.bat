@echo off
chcp 65001 >nul
cd /d "%~dp0.."

echo ========================================
echo   启动 MySQL 容器
echo ========================================

echo.
echo 正在启动 MySQL...
docker compose up -d mysql

echo.
echo 等待 MySQL 就绪...
:wait
docker compose exec -T mysql mysqladmin ping -h localhost -u root -proot --silent >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    <nul set /p =.
    timeout /t 3 /nobreak >nul
    goto wait
)

echo.
echo MySQL 已就绪 ✓

echo.
echo ========================================
echo   MySQL 已启动
echo   地址: 127.0.0.1:3306
echo   用户: root
echo   密码: root
echo ========================================
