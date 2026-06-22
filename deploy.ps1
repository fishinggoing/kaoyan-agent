# GradSchool Advisor — 服务器部署脚本
#
# 用法: 以管理员身份打开 PowerShell，cd 到项目目录，运行:
#   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
#   .\deploy.ps1
#
# 前置条件: Python 3.11+ 已安装 (https://www.python.org/downloads/)

$ErrorActionPreference = "Stop"
$projectDir = $PSScriptRoot
$port = 8000

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  GradSchool Advisor — 服务器部署" -ForegroundColor Cyan
Write-Host "  考研智能决策系统" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# ── 1. 检查 Python ──────────────────────────────────────────────────────
Write-Host "[1/6] 检查 Python..." -ForegroundColor Green

$python = $null
try { $python = (Get-Command python -ErrorAction Stop).Source }
catch {
    try { $python = (Get-Command python3 -ErrorAction Stop).Source }
    catch {
        Write-Host "[错误] 未找到 Python。请先安装 Python 3.11+:" -ForegroundColor Red
        Write-Host "  https://www.python.org/downloads/" -ForegroundColor Yellow
        Write-Host "  安装时务必勾选 'Add Python to PATH'" -ForegroundColor Yellow
        exit 1
    }
}

$pyVersion = & $python --version 2>&1
Write-Host "  找到: $pyVersion ($python)" -ForegroundColor Gray

# ── 2. 创建虚拟环境 ────────────────────────────────────────────────────
Write-Host "[2/6] 创建虚拟环境..." -ForegroundColor Green

$venvDir = Join-Path $projectDir ".venv"
if (Test-Path $venvDir) {
    Write-Host "  虚拟环境已存在，跳过创建" -ForegroundColor Gray
} else {
    & $python -m venv $venvDir
    Write-Host "  虚拟环境创建完成" -ForegroundColor Gray
}

$pip = Join-Path $venvDir "Scripts\pip.exe"
$pythonExe = Join-Path $venvDir "Scripts\python.exe"

# ── 3. 安装依赖 ────────────────────────────────────────────────────────
Write-Host "[3/6] 安装 Python 依赖（视网络速度，约 2-5 分钟）..." -ForegroundColor Green
$requirementsFile = Join-Path $projectDir "backend\requirements.txt"
if (Test-Path $requirementsFile) {
    & $pip install -r $requirementsFile --quiet
    Write-Host "  依赖安装完成" -ForegroundColor Gray
} else {
    Write-Host "[错误] 找不到 backend\requirements.txt" -ForegroundColor Red
    exit 1
}

# ── 4. 检测局域网 IP ───────────────────────────────────────────────────
Write-Host "[4/6] 检测本机局域网 IP..." -ForegroundColor Green

$lanIp = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object {
    $_.IPAddress -notlike "127.*" -and
    $_.IPAddress -notlike "169.254.*" -and
    $_.PrefixOrigin -ne "WellKnown"
} | Select-Object -First 1).IPAddress

if (-not $lanIp) {
    $lanIp = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object {
        $_.IPAddress -notlike "127.*"
    } | Select-Object -First 1).IPAddress
}

if (-not $lanIp) {
    $lanIp = "localhost"
}

Write-Host "  局域网 IP: $lanIp" -ForegroundColor Yellow

# ── 5. 配置 .env ───────────────────────────────────────────────────────
Write-Host "[5/6] 配置 .env 文件..." -ForegroundColor Green

$envFile = Join-Path $projectDir ".env"
$envContent = @"
# GradSchool Advisor - 服务器配置 (由 deploy.ps1 自动生成)
DEEPSEEK_API_KEY=your-api-key-here
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat
DATABASE_URL=sqlite:///./gradschool.db
CHROMA_PERSIST_DIR=./chroma_data
HOST=0.0.0.0
PORT=$port
DEBUG=false
ALLOW_ORIGINS=http://localhost:5173,http://localhost:$port,http://${lanIp}:$port
STATIC_DIR=../frontend/dist
"@

Set-Content -Path $envFile -Value $envContent -Encoding UTF8
Write-Host "  .env 已生成 (CORS 已包含 $lanIp)" -ForegroundColor Gray
Write-Host "  如果你有 DeepSeek API Key，请编辑 .env 填入 DEEPSEEK_API_KEY" -ForegroundColor Yellow

# ── 6. 防火墙 ──────────────────────────────────────────────────────────
Write-Host "[6/6] 配置防火墙..." -ForegroundColor Green

$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")

if (-not $isAdmin) {
    Write-Host "  [警告] 未以管理员身份运行，跳过防火墙配置" -ForegroundColor Yellow
    Write-Host "  请以管理员身份运行: .\setup-firewall.ps1" -ForegroundColor Yellow
} else {
    $ruleName = "GradSchool Advisor (Port $port)"
    $existing = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
    if ($existing) {
        Remove-NetFirewallRule -DisplayName $ruleName
    }
    New-NetFirewallRule -DisplayName $ruleName `
        -Direction Inbound -Protocol TCP -LocalPort $port `
        -Action Allow -Profile Private,Public `
        -Description "Allow inbound for GradSchool Advisor" | Out-Null
    Write-Host "  防火墙规则已添加 (TCP $port 入站)" -ForegroundColor Gray
}

# ── 验证 ───────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  部署完成！" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "启动命令:" -ForegroundColor Yellow
Write-Host "  cd $projectDir\backend" -ForegroundColor White
Write-Host "  $pythonExe -m uvicorn app.main:app --host 0.0.0.0 --port $port" -ForegroundColor White
Write-Host ""
Write-Host "或直接运行:" -ForegroundColor Yellow
Write-Host "  $projectDir\start-prod.bat" -ForegroundColor White
Write-Host ""
Write-Host "局域网访问地址:" -ForegroundColor Yellow
Write-Host "  http://${lanIp}:${port}" -ForegroundColor Cyan
Write-Host ""
Write-Host "API 文档:  http://${lanIp}:${port}/docs" -ForegroundColor Gray
Write-Host "健康检查:  http://${lanIp}:${port}/api/health" -ForegroundColor Gray
Write-Host ""

# 快速验证
Write-Host "正在启动服务器进行验证..." -ForegroundColor Green
$proc = Start-Process -FilePath $pythonExe `
    -ArgumentList "-B", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "$port" `
    -WorkingDirectory (Join-Path $projectDir "backend") `
    -PassThru `
    -WindowStyle Hidden

Start-Sleep -Seconds 4

try {
    $result = Invoke-WebRequest -Uri "http://localhost:$port/api/health" -UseBasicParsing -TimeoutSec 5
    $json = $result.Content | ConvertFrom-Json
    if ($json.success) {
        Write-Host "验证通过！API 响应正常" -ForegroundColor Green
    }
} catch {
    Write-Host "[警告] 验证失败：$_" -ForegroundColor Yellow
    Write-Host "请手动检查上述启动命令的输出" -ForegroundColor Yellow
}

# 不关服务器，留给用户决定
Write-Host ""
Write-Host "服务器正在后台运行 (PID: $($proc.Id))" -ForegroundColor Green
Write-Host "用浏览器打开 http://${lanIp}:${port} 即可访问" -ForegroundColor Cyan
Write-Host ""
Write-Host "停止服务器: Stop-Process -Id $($proc.Id)" -ForegroundColor Gray
Write-Host ""

Read-Host "按 Enter 退出（服务器会继续在后台运行）"
