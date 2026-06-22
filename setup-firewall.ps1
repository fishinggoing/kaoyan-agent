# GradSchool Advisor — Windows 防火墙配置
# 以管理员身份运行此脚本：右键 → 以管理员身份运行 PowerShell，然后执行：
#   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
#   .\setup-firewall.ps1

$port = 8000
$ruleName = "GradSchool Advisor (Port $port)"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  GradSchool Advisor — 防火墙配置" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 检查管理员权限
if (-NOT ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
    Write-Host "[错误] 请以管理员身份运行此脚本" -ForegroundColor Red
    Write-Host "  方法: 右键 PowerShell → 以管理员身份运行" -ForegroundColor Yellow
    pause
    exit 1
}

# 检查此端口是否已有规则
$existing = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "[信息] 防火墙规则已存在，正在删除旧规则..." -ForegroundColor Yellow
    Remove-NetFirewallRule -DisplayName $ruleName
}

# 添加入站规则
Write-Host "[1/2] 添加入站规则 (TCP $port)..." -ForegroundColor Green
New-NetFirewallRule -DisplayName $ruleName `
    -Direction Inbound `
    -Protocol TCP `
    -LocalPort $port `
    -Action Allow `
    -Profile Private,Public `
    -Description "Allow inbound traffic for GradSchool Advisor web app"

# 验证
$rule = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
if ($rule) {
    Write-Host "[2/2] 防火墙规则配置成功！" -ForegroundColor Green
    Write-Host ""
    Write-Host "规则详情:" -ForegroundColor Cyan
    Write-Host "  名称: $($rule.DisplayName)"
    Write-Host "  端口: $port"
    Write-Host "  协议: TCP"
    Write-Host "  方向: 入站"
    Write-Host "  状态: $($rule.Enabled -eq 'True' ? '已启用' : '未启用')"
} else {
    Write-Host "[错误] 防火墙规则添加失败" -ForegroundColor Red
    pause
    exit 1
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "配置完成！局域网内其他设备可通过以下地址访问：" -ForegroundColor Green

# 显示本机IP
$ips = Get-NetIPAddress -AddressFamily IPv4 | Where-Object {
    $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.254.*"
} | Select-Object -ExpandProperty IPAddress

foreach ($ip in $ips) {
    Write-Host "  http://${ip}:${port}" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "如需删除此规则，运行：" -ForegroundColor Gray
Write-Host "  Remove-NetFirewallRule -DisplayName '$ruleName'" -ForegroundColor Gray
Write-Host ""
pause
