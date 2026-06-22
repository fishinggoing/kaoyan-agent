# 安全审查报告 — GradSchool Advisor

> 审查日期: 2026-06-05  
> 审查范围: 全部代码库 (backend, frontend, scripts, config, docs)  
> **本报告不修改任何代码，仅提供发现问题与对策方案**

---

## 一、问题总览

| 等级 | 数量 | 风险描述 |
|------|------|---------|
| 🔴 严重 | 3 | API密钥泄露、零认证、全部端点无保护 |
| 🟠 高危 | 5 | 会话泄露、SSL禁用、CORS过于宽松 |
| 🟡 中危 | 8 | SSRF风险、错误信息泄露、输入验证不足 |
| 🔵 低危 | 5 | 安全头缺失、速率限制缺失、防火墙配置 |

---

## 二、🔴 严重问题

### C-1: DeepSeek API Key 明文存储在 .env 中

**文件**: `.env` 第2行  
**内容**: `DEEPSEEK_API_KEY=sk-********...`（已被替换为占位符）

这是**真实可用的 API Key**，任何能访问这台机器的人都可以：
- 用你的额度无限制调用 DeepSeek API
- 产生财务损失（DeepSeek 按量计费）
- 如果有日用量限制，耗尽你的配额导致服务不可用

**该 Key 已在以下 4 个 Agent 中全局使用**:
- `backend/app/agents/orchestrator.py` (行 129)
- `backend/app/agents/needs_analysis.py` (行 90)
- `backend/app/agents/pipeline_agent.py` (行 64)
- `backend/app/agents/school_enricher.py` (行 64)

> ⚠️ **更严重的是**: 你之前在聊天中又泄露了一个 GitHub Token (`ghp_YRIh...`)，该 token 也**必须立即吊销**。

---

### C-2: 所有 API 端点零认证、零授权

**范围**: 整个 API 层 (14 个路由模块, 约 40+ 端点)

当前状态：
- 无 JWT/Token 认证
- 无 API Key 校验
- 无 Session 管理
- 无用户登录/注册
- `bcrypt==5.0.0` 已安装但**代码中从未使用**（死依赖）
- `UserProfile` 模型**没有密码字段**

**影响**: 任何能访问 `http://服务器IP:8000` 的人可以:
- 增删改查所有用户资料
- 触发 AI 推荐（消耗 API 费用）
- 创建/运行学校监控
- 访问所有系统数据

---

### C-3: 项目无 Git 历史保护

仓库刚 `git init`，尚未 commit。这意味着：
- 所有密钥泄露尚未进入 Git 历史
- **现在就是在提交前清理的最佳时机**

---

## 三、🟠 高危问题

### H-1: 第三方网站 Session Cookie 泄露

**文件**: `tmp_cookies.txt`  
**内容**: `yantu.com.cn ... PHPSESSID 00b0667d0bc95d439f866a6b81def18f`

这是研招网/岩土网的 PHP Session ID，可用于会话劫持。

---

### H-2: SSL 证书验证被完全禁用

**文件**: `backend/app/services/monitor_service.py` 第 110-117 行

```python
_SSL_CONTEXT.check_hostname = False
_SSL_CONTEXT.verify_mode = ssl.CERT_NONE
_SSL_CONTEXT.set_ciphers("DEFAULT:@SECLEVEL=1")
```

所有监控服务的 HTTPS 请求都不验证证书，**包括向 ServerChan 发送通知的请求**。中间人攻击风险。

---

### H-3: CORS 配置过于宽松

**文件**: `backend/app/main.py` 第 48-56 行

```python
allow_credentials=True,
allow_methods=["*"],
allow_headers=["*"],
```

`allow_credentials=True` 配合通配符方法和头部，虽然 origins 限定了具体列表，但仍然扩大了攻击面。

---

### H-4: 敏感错误信息返回给客户端

**文件**: `backend/app/agents/orchestrator.py` 第 170 行、第 363 行

```python
analysis=f"推荐生成暂时不可用: {e}",  # 原始异常信息直接返回
```

LLM API 调用失败时，原始 Python 异常（可能含 API URL、内部路径）被直接嵌入 API 响应。

---

### H-5: asyncio.run() 在同步端点内调用

**文件**: `backend/app/api/pipeline.py` 第 77 行

```python
result, name_to_subjects = asyncio.run(decision_recommend(...))
```

在已有事件循环的环境中会抛出 `RuntimeError`（uvicorn 本身就是 async 运行时）。

---

## 四、🟡 中危问题

### M-1: SSRF 风险

`backend/app/services/monitor_service.py` 和 `crawl_service.py` 中的爬虫/监控服务会向用户可控的 URL 发出 HTTP 请求。`monitor_url` 通过 `POST /api/monitor/` 提交，仅做了基本的 URL 格式校验，未防御 SSRF。

### M-2: 输入验证缺失

`backend/app/api/needs_analysis.py` 第 158 行的 `save_weights` 端点接受原始 `dict` 而非 Pydantic Schema，无类型校验。

### M-3: LLM 输出直接反序列化

多个文件中 LLM 返回的 JSON 通过 `json.loads()` 直接解析，无 Schema 验证。如果 LLM 输出被操纵，可注入非预期数据结构。

### M-4: 临时文件污染根目录

8 个 `tmp_*` 文件 (共约 4MB) 散落在项目根目录，包含爬取的网站数据、登录页面 HTML、JS 包等。`.gitignore` 未排除 `tmp_*`。

### M-5: 环境变量无强制校验

`backend/app/config.py` 第 35-39 行仅在 API Key 缺失时打印 `warning` 而不阻止启动。

### M-6: ServerChan Key 嵌入 URL 路径

`backend/app/services/notify_service.py` 第 8 行: `SERVERCHAN_URL = "https://sctapi.ftqq.com/{key}.send"` — 密钥作为 URL 路径的一部分传输，会被代理日志和 HTTP 访问日志记录。

### M-7: 文档泄露密钥配置

`docs/CODEMAPS/integrations.md` 第 110-121 行记录了完整的环境变量 schema，包括 `DEEPSEEK_API_KEY` 和 `SERVERCHAN_KEY`。

### M-8: 数据库迁移脚本使用原始 SQL

`backend/scripts/add_preference_weights.py` 第 17 行使用未参数化的 SQL 字符串。

---

## 五、🔵 低危问题

### L-1: 安全头不完整

`backend/app/main.py` 第 36-43 行的 `SecurityHeadersMiddleware` 缺少:
- `Content-Security-Policy`
- `Strict-Transport-Security` (HSTS)

### L-2: 无速率限制

AI 调用端点 (`/api/decisions/*`, `/api/pipeline/*`, `/api/needs-analysis/*`) 无限流保护，可被滥用产生费用。

### L-3: 防火墙规则过于宽松

`setup-firewall.ps1` 将端口 8000 开放到 **Public** 防火墙 Profile，意味着在咖啡店、酒店等公共网络也可访问。

### L-4: Vite 开发服务器允许 Ngrok 隧道

`frontend/vite.config.ts` 第 10 行显式允许 ngrok 域名，开发模式下可将本地服务暴露到公网。

### L-5: 绑定 0.0.0.0

所有启动脚本 (`start.sh`, `start.bat`, `start-prod.bat`, `deploy.ps1`) 都绑定所有网络接口。

---

## 六、云服务器安全加固方案

### 阶段 1: 立即执行 (部署前必须)

#### 1.1 密钥轮换

```bash
# 1. 登录 DeepSeek 控制台，重新生成 API Key
#    https://platform.deepseek.com/api_keys
# 2. 吊销旧 Key: 已在 .env 中更新

# 3. 吊销 GitHub Token
#    https://github.com/settings/tokens
#    删除之前泄露的 token，生成新的

# 4. 更新 .env 中的新 Key
```

#### 1.2 敏感文件清理

```bash
# 删除所有临时文件
rm -f tmp_*.txt tmp_*.html tmp_*.json tmp_*.js

# 将 tmp_* 加入 .gitignore (手动编辑)
echo "tmp_*" >> .gitignore
echo "*.log" >> .gitignore
```

#### 1.3 环境变量外置

**在云服务器上不要用项目目录下的 `.env`**。改用以下方案之一：

**方案 A: Systemd 环境变量 (推荐)**
```ini
# /etc/systemd/system/gradschool.service
[Service]
Environment="DEEPSEEK_API_KEY=sk-new-key-here"
Environment="SERVERCHAN_KEY=your-key"
EnvironmentFile=/etc/gradschool/secrets.env  # 权限 600
```

**方案 B: 使用 .env.example 模板**
```
# 项目中只保留 .env.example (不含真实密钥)
DEEPSEEK_API_KEY=your-api-key-here
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
...
```
真正的 `.env` 放在项目目录外，通过环境变量或启动参数指定路径。

#### 1.4 配置 .gitignore（未做，你自己编辑文件）

```
# 追加到 .gitignore
tmp_*
*.log
.pytest_cache/
.env.local
.env.production
```

---

### 阶段 2: 基础安全加固

#### 2.1 添加 API Key 认证中间件

**概念**: 在 `backend/app/middleware/` 新建 `auth.py`

```python
# 伪代码 — 具体实现由你决定
from fastapi import Header, HTTPException

async def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key != settings.api_key:  # 从环境变量读取
        raise HTTPException(403, "Invalid API Key")

# 在 router 级别应用
router = APIRouter(dependencies=[Depends(verify_api_key)])
```

#### 2.2 添加速率限制

使用 `slowapi` 库（与 FastAPI 兼容）:

```bash
pip install slowapi
```

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

# 对 AI 端点限制
@router.post("/recommend")
@limiter.limit("5/minute")
async def recommend(...):
    ...
```

#### 2.3 修复 SSL 证书验证

`monitor_service.py` 中应该**仅对大学网站**使用宽松的 SSL 上下文，而非全局:

```python
# 为监控目标单独创建宽松上下文
LEGACY_SSL = httpx.create_ssl_context()
LEGACY_SSL.check_hostname = False
LEGACY_SSL.verify_mode = ssl.CERT_NONE

# 向 ServerChan 发通知用标准 SSL
async with httpx.AsyncClient() as client:  # 默认验证证书
    await client.post(SERVERCHAN_URL, ...)

# 仅爬虫用宽松上下文
async with httpx.AsyncClient(verify=LEGACY_SSL) as client:
    await client.get(school_url, ...)
```

#### 2.4 错误信息脱敏

将所有 `f"错误: {e}"` 改为:

```python
logger.error(f"LLM API call failed: {e}")  # 完整错误记日志
return "AI 服务暂时不可用，请稍后重试"        # 客户端只看到模糊信息
```

---

### 阶段 3: 生产级安全

#### 3.1 Nginx 反向代理 + HTTPS

```nginx
# /etc/nginx/sites-available/gradschool
server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate     /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    # 安全头
    add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'nonce-{RANDOM}'; style-src 'self' 'unsafe-inline';";
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload";
    add_header X-Content-Type-Options "nosniff";
    add_header X-Frame-Options "DENY";

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        # 速率限制
        limit_req zone=api burst=10 nodelay;
    }
}

# 速率限制区
limit_req_zone $binary_remote_addr zone=api:10m rate=5r/s;
```

#### 3.2 防火墙最小化

```bash
# 云服务器上仅开放 443 (HTTPS) 和 22 (SSH)
# 8000 端口只允许本地回环
ufw allow 443/tcp
ufw allow 22/tcp
ufw deny 8000/tcp   # 禁止外部直接访问后端
ufw enable
```

#### 3.3 非 root 用户运行

```bash
# 创建服务专用用户
useradd -r -s /bin/false gradschool
# systemd 服务以该用户运行
```

#### 3.4 完整安全头

在 Nginx 或应用层补充:
- `Content-Security-Policy` (阻止 XSS)
- `Strict-Transport-Security` (强制 HTTPS)
- `X-XSS-Protection: 1; mode=block`
- `Cache-Control: no-store` (敏感 API 响应)

#### 3.5 日志和审计

```python
# 在中间件中添加请求日志
import logging
logger = logging.getLogger("audit")
logger.info(f"{request.client.host} {request.method} {request.url.path}")
```

---

### 阶段 4: 持续安全

#### 4.1 定期依赖扫描

```bash
# Python
pip-audit
# 或
safety check

# JavaScript
npm audit
```

#### 4.2 安全扫描工具

```bash
# Python 静态安全分析
pip install bandit
bandit -r backend/app/

# 密钥扫描 (防止误提交)
pip install detect-secrets
detect-secrets scan --all-files
```

#### 4.3 Git Pre-commit Hook

```bash
# .git/hooks/pre-commit
#!/bin/bash
# 阻止提交包含 API Key 的代码
if grep -r "sk-[a-zA-Z0-9]\{20,\}" --include="*.py" --include="*.env" .; then
    echo "ERROR: API key detected in staged files!"
    exit 1
fi
```

#### 4.4 监控与告警

- 设置 DeepSeek API 用量告警（日消费上限）
- 监控 `/api/health` 端点可用性
- 异常流量检测（短时间内大量 AI 调用）

---

## 七、优先级时间线

| 优先级 | 事项 | 预期耗时 | 部署前必做 |
|--------|------|---------|-----------|
| P0 | 轮换 DeepSeek API Key | 5 分钟 | ✅ 是 |
| P0 | 吊销泄露的 GitHub Token | 5 分钟 | ✅ 是 |
| P0 | 删除 tmp_* 文件，更新 .gitignore | 2 分钟 | ✅ 是 |
| P0 | 环境变量外置（不放在项目目录） | 15 分钟 | ✅ 是 |
| P1 | 添加 API Key 认证中间件 | 1 小时 | ✅ 推荐 |
| P1 | 添加速率限制 | 30 分钟 | ✅ 推荐 |
| P1 | 错误信息脱敏 | 15 分钟 | ⬜ 建议 |
| P1 | 修复 SSL 混用问题 | 15 分钟 | ⬜ 建议 |
| P2 | 配置 Nginx + HTTPS | 2 小时 | ⬜ 建议 |
| P2 | 云服务器防火墙配置 | 30 分钟 | ⬜ 建议 |
| P2 | 完整安全头 | 15 分钟 | ⬜ 建议 |
| P3 | 非 root 用户运行 | 15 分钟 | ⬜ 可选 |
| P3 | 依赖安全扫描 | 10 分钟 | ⬜ 可选 |
| P3 | Git pre-commit hook | 10 分钟 | ⬜ 可选 |

---

> **注意**: 本报告仅提供问题分析和安全方案建议，不直接修改任何代码。  
> 建议按优先级逐项实施，每完成一个阶段做一次安全验证。
