@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ========================================
echo   GradSchool Advisor — 生产模式
echo   考研智能决策系统
echo ========================================
echo.

REM 检查 Python 虚拟环境
if not exist "%~dp0.venv\Scripts\python.exe" (
    echo [X] 错误: 未找到 Python 虚拟环境
    echo.
    echo 请先运行部署脚本（以管理员身份打开 PowerShell）:
    echo   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
    echo   .\deploy.ps1
    echo.
    echo 或手动创建虚拟环境:
    echo   python -m venv .venv
    echo   .venv\Scripts\pip install -r backend\requirements.txt
    echo.
    pause
    exit /b 1
)

REM 检查前端是否已构建
if not exist "%~dp0frontend\dist\index.html" (
    echo [!] 前端尚未构建，正在构建...
    cd /d "%~dp0frontend"
    call npm install --silent 2>nul
    call npm run build
    if %ERRORLEVEL% NEQ 0 (
        echo [X] 前端构建失败！请确认已安装 Node.js
        echo 如果服务器上没有 Node.js，请在开发机上构建好 dist/ 再拷贝过来
        pause
        exit /b 1
    )
    echo 前端构建完成
    cd /d "%~dp0"
)

REM 获取本机 IP（使用 PowerShell）
for /f "usebackq delims=" %%a in (`powershell -Command "(Get-NetIPAddress -AddressFamily IPv4 ^| Where-Object {$_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*'} ^| Select-Object -First 1).IPAddress" 2^>nul`) do set "LAN_IP=%%a"
if "%LAN_IP%"=="" set LAN_IP=localhost

echo 本机 IP: %LAN_IP%
echo 访问地址: http://%LAN_IP%:8000
echo API 文档: http://%LAN_IP%:8000/docs
echo.

REM 读取 .env 中的 PORT（如果存在）
set PORT=8000
if exist "%~dp0.env" (
    for /f "tokens=2 delims==" %%a in ('findstr /b "PORT=" "%~dp0.env" 2^>nul') do set PORT=%%a
)

echo 启动后端服务器 (0.0.0.0:%PORT%)...
echo 按 Ctrl+C 停止服务器
echo ========================================
echo.

cd /d "%~dp0backend"
"%~dp0.venv\Scripts\python.exe" -B -m uvicorn app.main:app --host 0.0.0.0 --port %PORT% --no-access-log

pause
