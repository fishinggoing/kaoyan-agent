# 待修复问题清单

> 保存时间: 2026-06-01 | 来源: 代码审查报告

---

## 🔴 CRITICAL（3项）

| # | 问题 | 位置 |
|---|------|------|
| C1 | 所有写操作和 LLM 端点无认证 | `backend/app/api/*.py` |
| C2 | 无 CSRF 保护 | `backend/app/main.py` |
| C3 | 无速率限制，LLM 端点可被滥用 | `/api/decisions/*`, `/api/pipeline/*`, `/api/needs-analysis/*` |

## 🟠 HIGH（11项）

| # | 问题 | 位置 |
|---|------|------|
| H1 | `decision_service.py` 文件过大 (1184行) | `backend/app/services/decision_service.py` |
| H2 | `recommend()` 函数过长 (354行) | `decision_service.py:246-599` |
| H3 | `recommend_by_school_names()` 过长 (282行) | `decision_service.py:902-1183` |
| H4 | 同步 SQLAlchemy 用于 async 路由 | 所有 `backend/app/api/*.py` |
| H5 | 重复的 profile 序列化代码 | `api/pipeline.py` + `api/profiles.py` |
| H6 | 重复的趋势分析函数 | `score_service.py` + `decision_service.py` |
| H7 | 深层嵌套 5-6 层 | `decision_service.py:313-395` |
| H8 | 可变默认参数 | `backend/app/agents/needs_analysis.py:256` |
| H9 | 所有 POST/PUT 接受 raw dict 无校验 | 所有 `backend/app/api/*.py` |
| H10 | TypeScript strict 模式未启用 | `frontend/tsconfig.app.json` |
| H11 | 无安全响应头 (HSTS/CSP/XFO) | `backend/app/main.py` |

## 🟡 MEDIUM（8项）

| # | 问题 | 位置 |
|---|------|------|
| M1 | SQLAlchemy 1.x 风格混用 | `backend/scripts/fix_school_levels.py:62` |
| M2 | 测试 DB 用文件而非内存 | `backend/tests/conftest.py:58` |
| M3 | 重复的 cache save 逻辑 | `decision_service.py:574-592, 1158-1176` |
| M4 | API 无 Pydantic 请求/响应模型 | 所有 API 端点 |
| M5 | E2E 测试覆盖不足 | `frontend/e2e/*.spec.ts` |
| M6 | `start.sh` 用 Windows 路径 | `start.sh:13` |
| M7 | 数据库/ChromaDB 用相对路径 | `.env` |
| M8 | Stale closure in DecisionPage | `frontend/src/pages/DecisionPage.tsx:117-123` |

---

## 修复优先级建议

1. H9 → 添加 Pydantic 请求模型（安全+质量）
2. H1-H7 → 重构 decision_service.py
3. C1-C3 → 认证/CSRF/限流
4. H10 → TypeScript strict 模式
5. H11 → 安全响应头
6. M1-M8 → 低优先级改进
