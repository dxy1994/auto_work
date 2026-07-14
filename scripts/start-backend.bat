@echo off
chcp 65001 >nul
setlocal

set "BACKEND_DIR=%~dp0..\backend"

echo ========================================
echo   后端服务启动（物理机模式）
echo ========================================

:: 1. 检查 Java 与 Maven
echo.
echo [1/2] 检查 Java 与 Maven...
where java >nul 2>&1 || (echo        未找到 Java 17 & exit /b 1)
where mvn >nul 2>&1 || (echo        未找到 Maven & exit /b 1)
echo        Java 与 Maven 已就绪

:: 2. 启动后端服务
echo.
echo [2/2] 启动 Spring Boot 后端服务...
echo.
echo ========================================
echo   后端: http://localhost:8000
echo   健康检查: http://localhost:8000/api/health
echo   按 Ctrl+C 停止服务
echo ========================================
echo.

cd /d "%BACKEND_DIR%"
mvn spring-boot:run
pause
