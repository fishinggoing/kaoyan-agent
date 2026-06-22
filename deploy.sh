#!/usr/bin/env bash
# ============================================
# GradSchool Advisor — Linux 服务器部署脚本
# 适用于: Ubuntu 20.04+ / Debian 11+ / CentOS 8+
# ============================================
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
PORT=8000
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${CYAN}========================================"
echo "  GradSchool Advisor — 服务器部署"
echo "  考研智能决策系统"
echo -e "========================================${NC}"
echo ""

# ── 检测包管理器 ──────────────────────────────────────────────────
if command -v apt &>/dev/null; then
    PKG_MGR="apt"
elif command -v dnf &>/dev/null; then
    PKG_MGR="dnf"
elif command -v yum &>/dev/null; then
    PKG_MGR="yum"
else
    echo -e "${RED}[错误] 无法检测包管理器 (apt/dnf/yum)${NC}"
    exit 1
fi

# ── 1. 安装系统依赖 ───────────────────────────────────────────────
echo -e "${GREEN}[1/6] 安装系统依赖...${NC}"

if [ "$PKG_MGR" = "apt" ]; then
    sudo apt update -qq
    sudo apt install -y -qq python3 python3-venv python3-pip curl 2>/dev/null
else
    sudo $PKG_MGR install -y python3 python3-pip curl 2>/dev/null
fi

PYTHON=$(command -v python3)
echo -e "  Python: $($PYTHON --version 2>&1)"

# ── 2. 创建虚拟环境 ────────────────────────────────────────────────
echo -e "${GREEN}[2/6] 创建虚拟环境...${NC}"

VENV_DIR="$PROJECT_DIR/.venv"
if [ -d "$VENV_DIR" ]; then
    echo "  虚拟环境已存在，跳过"
else
    $PYTHON -m venv "$VENV_DIR"
    echo "  虚拟环境创建完成"
fi

PIP="$VENV_DIR/bin/pip"
PYTHON_VENV="$VENV_DIR/bin/python"

# ── 3. 安装 Python 依赖 ────────────────────────────────────────────
echo -e "${GREEN}[3/6] 安装 Python 依赖...${NC}"

REQ_FILE="$PROJECT_DIR/backend/requirements.txt"
if [ -f "$REQ_FILE" ]; then
    "$PIP" install --upgrade pip -q
    "$PIP" install -r "$REQ_FILE" -q
    echo "  依赖安装完成"
else
    echo -e "${RED}[错误] 找不到 backend/requirements.txt${NC}"
    exit 1
fi

# ── 4. 配置 .env ───────────────────────────────────────────────────
echo -e "${GREEN}[4/6] 配置 .env...${NC}"

ENV_DIR="$HOME/.gradschool"
ENV_FILE="$ENV_DIR/.env"
if [ ! -f "$ENV_FILE" ]; then
    mkdir -p "$ENV_DIR"
    cat > "$ENV_FILE" <<ENVEOF
# GradSchool Advisor — 服务器配置
DEEPSEEK_API_KEY=your-api-key-here
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat
DATABASE_URL=sqlite:///./gradschool.db
CHROMA_PERSIST_DIR=./chroma_data
HOST=0.0.0.0
PORT=$PORT
DEBUG=false
ALLOW_ORIGINS=http://localhost:$PORT
STATIC_DIR=../frontend/dist
API_KEY=your-secret-api-key-here
SERVERCHAN_KEY=
ENVEOF
    echo "  .env 已生成在 $ENV_FILE"
    echo -e "  ${YELLOW}vim $ENV_FILE${NC}"
else
    echo "  $ENV_FILE 已存在，跳过"
fi

# ── 5. 配置 systemd 服务 ───────────────────────────────────────────
echo -e "${GREEN}[5/6] 配置 systemd 服务 (开机自启)...${NC}"

SERVICE_FILE="/etc/systemd/system/gradschool.service"

if [ ! -f "$SERVICE_FILE" ]; then
    sudo tee "$SERVICE_FILE" > /dev/null <<SVCEOF
[Unit]
Description=GradSchool Advisor - 考研智能决策系统
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$PROJECT_DIR/backend
ExecStart=$PYTHON_VENV -B -m uvicorn app.main:app --host 0.0.0.0 --port $PORT --no-access-log
Restart=always
RestartSec=5
Environment=PATH=$VENV_DIR/bin:/usr/bin

[Install]
WantedBy=multi-user.target
SVCEOF
    sudo systemctl daemon-reload
    sudo systemctl enable gradschool.service
    echo "  systemd 服务已创建: gradschool.service"
else
    echo "  systemd 服务已存在，跳过"
fi

# ── 6. 防火墙 ──────────────────────────────────────────────────────
echo -e "${GREEN}[6/6] 配置防火墙...${NC}"

# ufw (Ubuntu)
if command -v ufw &>/dev/null; then
    sudo ufw allow $PORT/tcp 2>/dev/null || true
    echo "  ufw: 已放行端口 $PORT"
fi

# firewalld (CentOS/RHEL)
if command -v firewall-cmd &>/dev/null; then
    sudo firewall-cmd --permanent --add-port=$PORT/tcp 2>/dev/null || true
    sudo firewall-cmd --reload 2>/dev/null || true
    echo "  firewalld: 已放行端口 $PORT"
fi

echo ""
echo "⚠️  重要提醒: 还需要去 腾讯云控制台 → 安全组 → 添加入站规则"
echo "   协议: TCP  端口: $PORT  来源: 0.0.0.0/0"
echo ""

# ── 启动服务 ──────────────────────────────────────────────────────
echo -e "${CYAN}========================================"
echo "  部署完成！"
echo -e "========================================${NC}"
echo ""
echo "启动服务:"
echo -e "  ${YELLOW}sudo systemctl start gradschool${NC}"
echo ""
echo "查看状态:"
echo -e "  ${YELLOW}sudo systemctl status gradschool${NC}"
echo ""
echo "查看日志:"
echo -e "  ${YELLOW}sudo journalctl -u gradschool -f${NC}"
echo ""
echo "访问地址:"
echo -e "  ${CYAN}http://$(hostname -I 2>/dev/null || echo 'YOUR_SERVER_IP'):$PORT${NC}"
echo -e "  ${CYAN}API 文档: http://$(hostname -I 2>/dev/null || echo 'YOUR_SERVER_IP'):$PORT/docs${NC}"
echo -e "  ${CYAN}健康检查: http://$(hostname -I 2>/dev/null || echo 'YOUR_SERVER_IP'):$PORT/api/health${NC}"
echo ""
