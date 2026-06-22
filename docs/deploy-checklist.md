# 云服务器部署清单

> 按顺序执行，每步约需时间标注在标题后

---

## 步骤 1: 生成 API Key (2 分钟)

在你的 Windows 电脑上打开 PowerShell，生成两个随机密钥：

```powershell
# 1. API Key (用于保护后端写操作和AI端点)
powershell -Command "[Convert]::ToHexString((New-Object Security.Cryptography.RNGCryptoServiceProvider).GetBytes(32))"

# 2. 复制输出结果，那是一串64位的十六进制字符串，例如:
#    A3F8C21D9E4B... (你的会不一样)
```

把这串记下来，后面要用。

---

## 步骤 2: 更新本地 .env 文件 (2 分钟)

编辑 `E:\try-agent\.env`，添加一行：

```
API_KEY=你刚才生成的64位十六进制字符串
```

完整 .env 应该类似：

```
DEEPSEEK_API_KEY=sk-你的新key
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat
DATABASE_URL=sqlite:///./gradschool.db
CHROMA_PERSIST_DIR=./chroma_data
HOST=127.0.0.1
PORT=8000
DEBUG=false
ALLOW_ORIGINS=http://localhost:5173
STATIC_DIR=../frontend/dist
API_KEY=你生成的64位随机字符串
SERVERCHAN_KEY=
```

---

## 步骤 3: 构建前端 (3 分钟)

```powershell
cd E:\try-agent\frontend
npm install
# 把 API_KEY 传入 Vite 构建
$env:VITE_API_KEY = "你的API_KEY"
npm run build
```

构建完成后 `frontend/dist/` 目录就是生产用的静态文件。

---

## 步骤 4: 上传项目到云服务器 (5 分钟)

用你习惯的方式上传（scp、rsync、SFTP、Git 等）：

```bash
# 示例: scp 整个项目（排除 .venv 和 node_modules）
rsync -avz --exclude '.venv' --exclude 'node_modules' --exclude '.git' \
  /e/try-agent/ user@你的服务器IP:/home/user/gradschool/
```

> ⚠️ `.env` 文件会上传（含 API Key），确保服务器上 .env 文件权限为 600

---

## 步骤 5: 服务器环境准备 (10 分钟)

SSH 登录到云服务器后：

```bash
# 1. 安装 Python 3.11+ 和 Nginx
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3-pip nginx certbot python3-certbot-nginx

# 2. 创建服务用户
sudo useradd -r -s /bin/false gradschool

# 3. 创建虚拟环境
cd /home/user/gradschool
python3.11 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt

# 4. 设置 .env 文件权限
chmod 600 .env

# 5. 初始化数据库
.venv/bin/python -c "from app.db.database import engine, Base; from app.models import *; Base.metadata.create_all(bind=engine)"
# (在 backend/ 目录下运行)

# 6. 把项目目录权限给 gradschool 用户
sudo chown -R gradschool:gradschool /home/user/gradschool
```

---

## 步骤 6: 配置 Nginx + HTTPS (15 分钟)

### 6.1 先配置 HTTP（用于证书申请）

创建 `/etc/nginx/sites-available/gradschool`:

```nginx
# 速率限制区域定义（放在 http 块或 server 块外）
limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
limit_req_zone $binary_remote_addr zone=llm:10m rate=5r/m;

server {
    listen 80;
    server_name your-domain.com;  # 改成你的域名

    # 请求体大小限制
    client_max_body_size 1m;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # AI 端点更严格的速率限制
    location /api/decisions/ {
        limit_req zone=llm burst=3 nodelay;
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /api/pipeline/ {
        limit_req zone=llm burst=3 nodelay;
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # API 通用速率限制
    location /api/ {
        limit_req zone=api burst=20 nodelay;
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 6.2 启用站点并申请 SSL 证书

```bash
sudo ln -s /etc/nginx/sites-available/gradschool /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default  # 删除默认站点
sudo nginx -t                               # 检查配置语法
sudo systemctl reload nginx

# 申请 SSL 证书（需要域名已解析到服务器 IP）
sudo certbot --nginx -d your-domain.com

# 证书会自动续期（certbot 自带定时任务）
```

---

## 步骤 7: 配置防火墙 (5 分钟)

```bash
# 仅开放必要端口
sudo ufw allow 22/tcp       # SSH
sudo ufw allow 443/tcp      # HTTPS
sudo ufw allow 80/tcp       # HTTP (仅用于证书续期，之后可关)
sudo ufw deny 8000/tcp      # 禁止直接访问后端！
sudo ufw enable

# 确认规则
sudo ufw status verbose
```

---

## 步骤 8: 创建 systemd 服务 (5 分钟)

创建 `/etc/systemd/system/gradschool.service`:

```ini
[Unit]
Description=GradSchool Advisor Backend
After=network.target

[Service]
Type=simple
User=gradschool
Group=gradschool
WorkingDirectory=/home/user/gradschool/backend
EnvironmentFile=/home/user/gradschool/.env
ExecStart=/home/user/gradschool/.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
Restart=on-failure
RestartSec=5

# 安全加固
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/home/user/gradschool
ReadOnlyPaths=/home/user/gradschool/.env

[Install]
WantedBy=multi-user.target
```

启动服务：

```bash
sudo systemctl daemon-reload
sudo systemctl enable gradschool
sudo systemctl start gradschool
sudo systemctl status gradschool   # 确认 running
```

---

## 步骤 9: 验证 (3 分钟)

```bash
# 1. 健康检查
curl https://your-domain.com/api/health

# 2. 测试 API Key 认证（无 Key 应该返回 403）
curl -X POST https://your-domain.com/api/decisions/recommend \
  -H "Content-Type: application/json" \
  -d '{"profile_id": 1}'
# 预期: 403 Invalid or missing API key

# 3. 测试正确认证（应该正常返回）
curl -X POST https://your-domain.com/api/decisions/recommend \
  -H "Content-Type: application/json" \
  -H "X-API-Key: 你的API_KEY" \
  -d '{"profile_id": 1}'
# 预期: 正常 JSON 响应（可能因无数据返回空推荐）

# 4. 前端访问
# 浏览器打开 https://your-domain.com
```

---

## 步骤 10: 设置 DeepSeek 用量告警 (可选，2 分钟)

1. 登录 https://platform.deepseek.com
2. 进入 **用量管理 / Billing**
3. 设置**日消费上限**（建议 10-50 元/天，根据你的预算）
4. 开启**余额告警**

---

## 日常维护

| 频率 | 操作 | 命令 |
|------|------|------|
| 每周 | 检查服务状态 | `sudo systemctl status gradschool` |
| 每月 | 更新依赖 | `pip install -r requirements.txt --upgrade` |
| 每月 | 安全扫描 | `pip-audit` |
| 每季度 | 查看日志 | `sudo journalctl -u gradschool -n 100` |
| SSL证书 | 自动续期，无需操作 | certbot 自带 timer |

---

## 故障排查

```bash
# 服务启动失败？
sudo journalctl -u gradschool -n 50 --no-pager

# Nginx 报错？
sudo nginx -t
sudo tail -f /var/log/nginx/error.log

# 端口被占用？
sudo ss -tlnp | grep 8000

# API 返回 403？
# 检查 .env 中 API_KEY 是否设置
# 检查请求头 X-API-Key 是否正确
```
