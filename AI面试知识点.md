# AI 应用开发实习生面试知识点

> 基于个人项目（考研院校智能决策系统）的面试准备材料

---

## 目录

1. [HTTP 协议基础](#1-http-协议基础)
2. [LLM API 调用原理](#2-llm-api-调用原理)
3. [Prompt Engineering](#3-prompt-engineering)
4. [向量数据库与 RAG](#4-向量数据库与-rag)
5. [AI Agent 多代理编排](#5-ai-agent-多代理编排)

---

## 1. HTTP 协议基础

### Q1: HTTP 请求从发出到返回，中间发生了什么？

**面试标准回答：**

1. **DNS 解析**：浏览器将域名（如 `api.deepseek.com`）通过 DNS 服务转为 IP 地址
2. **TCP 三次握手**：客户端与服务器建立可靠连接
   - 客户端 → SYN → 服务器
   - 服务器 → SYN-ACK → 客户端
   - 客户端 → ACK → 服务器
3. **发送 HTTP 请求报文**：包含三个部分
   - **请求行**：`POST /v1/chat/completions HTTP/1.1`
   - **请求头（Headers）**：`Content-Type: application/json`、`Authorization: Bearer sk-xxx`
   - **请求体（Body）**：JSON 数据（如 messages 对话内容）
4. **服务器处理**：
   - Web 服务器（Nginx）接收请求，做反向代理
   - 转发给应用服务器（Uvicorn → FastAPI）
   - FastAPI 根据路径匹配路由，执行对应的 Python 函数
   - 函数内部可能查询数据库、调用外部 API、执行计算
5. **返回 HTTP 响应报文**：
   - **状态行**：`HTTP/1.1 200 OK`
   - **响应头**：`Content-Type: application/json`
   - **响应体**：JSON 数据
6. **浏览器渲染**（前端场景）：解析 HTML → 构建 DOM → 加载 CSS/JS → 渲染页面

**你项目中的实际例子：**

```
浏览器点击"开始分析"
  → POST /api/needs-analysis  (请求体: {"message": "我想考计算机"})
  → Nginx (49.233.176.135:80)
  → Uvicorn (127.0.0.1:8000)
  → FastAPI router → needs_analysis.py
  → DeepSeek API (HTTPS请求)
  → 返回 JSON → 前端渲染聊天气泡
```

---

### Q2: GET 和 POST 有什么区别？PUT 和 PATCH 呢？

| | GET | POST |
|---|-----|------|
| **用途** | 获取/读取数据 | 创建/提交数据 |
| **数据位置** | URL 查询参数 `?name=张三&page=1` | 请求体 Body（JSON/Form） |
| **幂等性** | 幂等：请求 10 次结果不变 | 不幂等：请求 10 次创建 10 条记录 |
| **缓存** | 浏览器可缓存 | 不缓存 |
| **URL 长度** | 有限制（约 2048 字符） | 无限制 |
| **安全性** | 参数暴露在 URL 中 | 参数在 Body 中，相对安全 |

**PUT vs PATCH：**
- **PUT**：全量替换。把整个资源完全替换成新数据，没传的字段会被清空/设默认值。
- **PATCH**：部分更新。只更新传过来的字段，其他字段保持不变。

**RESTful API 命名规范：**
```
GET    /api/schools          → 获取院校列表
GET    /api/schools/123      → 获取 id=123 的院校详情
POST   /api/schools          → 新增一个院校
PUT    /api/schools/123      → 全量更新 id=123 的院校
PATCH  /api/schools/123      → 部分更新 id=123 的院校
DELETE /api/schools/123      → 删除 id=123 的院校
```

**补充知识：幂等性**
- 幂等操作：执行 1 次和执行 100 次，结果一样。GET、PUT、DELETE 都是幂等的。
- 非幂等操作：每次执行都会产生新结果。POST 是非幂等的。

---

### Q3: HTTP 状态码分别什么意思？

| 状态码 | 含义 | 什么时候出现 |
|--------|------|-------------|
| **200** | OK，请求成功 | 正常返回数据 |
| **201** | Created，资源创建成功 | POST 新建数据后返回 |
| **301** | 永久重定向 | 旧 URL 永久迁移到新 URL，浏览器会缓存 |
| **302** | 临时重定向 | 临时跳转，浏览器不缓存 |
| **400** | Bad Request，请求参数有误 | 前端传了错误格式的数据 |
| **401** | Unauthorized，未认证 | 没传 API Key 或 API Key 错误 |
| **403** | Forbidden，无权限 | 认证了但没有操作权限 |
| **404** | Not Found，资源不存在 | 查一个不存在的 ID |
| **422** | Unprocessable Entity，参数校验失败 | Pydantic 校验不通过 |
| **429** | Too Many Requests，请求太频繁 | 触发速率限制（Rate Limit） |
| **500** | Internal Server Error，服务器内部错误 | 代码崩了、数据库挂了 |
| **502** | Bad Gateway，网关错误 | Nginx 连不上后端 Uvicorn |
| **503** | Service Unavailable，服务不可用 | 后端维护中或过载 |

**你项目中的实际使用：**

```python
# 200 — 正常返回
@app.get("/api/health")
async def health_check():
    return {"success": True, "data": {"status": "healthy"}, "error": None}

# 413 — 请求体太大
if int(content_length) > MAX_BODY_SIZE:
    return JSONResponse(status_code=413, ...)

# 503 — API Key 未配置
if not settings.api_key:
    logger.error("API_KEY is not set — protected endpoints will return 503")
```

---

## 2. LLM API 调用原理

### Q1: 调用 DeepSeek API 底层发生了什么？

**面试标准回答：**

> 本质是一次 HTTPS POST 请求，请求体包含 model、messages、temperature、max_tokens 等参数。
>
> 服务端处理流程：
> 1. **Tokenizer（BPE 分词算法）**：把 messages 里所有文字切分成 token IDs。一个中文字 ≈ 0.75 个 token，一个英文单词 ≈ 1.3 个 token。
>    - 输入 "我是河北工程大学的学生" → Tokenizer → `[1234, 5678, 9012, 3456, ...]`
> 2. **Transformer 推理**：token IDs 送入多层 Transformer 网络，每层做 Self-Attention 计算每个 token 和其他所有 token 的关系权重。最终输出每个位置下一个 token 的概率分布（几万个候选词各有一个概率）。
> 3. **自回归解码（Autoregressive Decoding）**：一个 token 一个 token 地预测，每次把新生成的 token 拼回输入序列，再预测下一个。直到遇到 EOS（结束符）或达到 max_tokens 上限。
> 4. **采样策略**：根据 temperature 参数决定选哪个 token：
>    - temperature=0（贪婪解码）：直接选概率最高的
>    - temperature>0：先除以 temperature 再 softmax，低保低选、高保高选
>    - top_p（核采样）：只从累积概率达到 p 的候选词里选，砍掉长尾噪声
> 5. **Detokenizer**：生成的 token IDs 转回可读文字
> 6. **流式返回**：如果 stream=true，每个 token 生成时立刻推送 SSE 事件；否则等全部完成一次返回

**关键概念补充：**

**Transformer 架构（简化理解）：**
```
输入 Token IDs
  → Embedding 层（每个 token 映射为一个向量 [1×d_model]）
  → N 层 Transformer Block（每层包含）：
       ├── Multi-Head Self-Attention（计算 token 之间的关联）
       ├── Add & LayerNorm（残差连接 + 层归一化）
       ├── Feed-Forward Network（全连接前馈网络）
       └── Add & LayerNorm
  → 输出层（线性投影 + Softmax → 每个候选词的概率）
```

**Self-Attention 直白理解：**
- 输入 "我 是 河北 工程 大学 的 学生"
- Self-Attention 计算每个词应该"关注"其他哪些词
- 比如"大学"这个词，注意力会集中在"河北"和"工程"上，因为它们是修饰关系
- 这就是为什么 LLM 能理解上下文——它不是孤立看每个词，而是看词之间的关系

---

### Q2: temperature 参数是什么？怎么选？

**面试标准回答：**

> temperature 控制模型输出的随机性/创造力。
>
> 原理：在 softmax 之前，把每个候选 token 的 logit 除以 temperature：
> ```
> P(token_i) = softmax(logit_i / T)
> ```
> - **T < 1（低 temperature）**：概率分布更"尖锐"，高分 token 概率被放大，模型更确定、输出更稳定
> - **T > 1（高 temperature）**：概率分布更"平坦"，低分 token 概率也会被提升，输出更多样化
> - **T = 0**：等价于贪婪解码，每步直接取最高概率 token（100% 确定性）
>
> 实际应用场景：
> - 数学计算、代码生成、数据分析 → temperature=0 或 0.1（需要确定性）
> - 对话助手、文本摘要 → temperature=0.3~0.5（平衡）
> - 创意写作、头脑风暴 → temperature=0.7~1.0（需要多样性）
>
> 我的择校系统用 temperature=0.4，因为推荐结果需要稳定一致——同一个考生两次询问应该得到相似的推荐。

**补充：为何不能让 temperature=1.0 做择校**
```
T=0.2: "建议你冲刺清华，稳妥报考北邮，保底河北工程" — 稳定，每次差不多
T=1.0: "建议你冲刺清华" 下次 "建议你报考北大" 再下次 "建议你出国" — 不可靠
```

---

### Q3: Token 是什么？为什么大模型按 Token 计费？

**面试标准回答：**

> Token 是 LLM 处理文本的最小单位，不是字也不是词。
>
> BPE（Byte Pair Encoding）分词算法：高频词整体作为一个 token，低频词会被拆成子词片段。
>
> 中文例子：约 1 个汉字 ≈ 0.75 token
> 英文例子："unbelievable" → "un" + "believe" + "able"（3 个 token）
>
> 计费原因：每个 token 都要经过完整的 Transformer 前向计算，计算量跟 token 数量成正比。所以按 token 计费。

**DeepSeek 计费参考（2026 年）：**
- deepseek-chat：输入约 ¥0.001/1K tokens，输出约 ¥0.002/1K tokens
- 一次择校推荐大约消耗 2000-5000 tokens（prompt 数据多），成本约几分钱

---

## 3. Prompt Engineering

### Q1: 你项目的 System Prompt 怎么设计的？

**面试标准回答：**

> 我的 System Prompt 包含三层结构：
>
> **第一层：角色设定**
> "你是一位资深的考研择校顾问专家" — 定义模型身份和行为边界，确保它不会跑题去聊别的。
>
> **第二层：输入说明**
> 告诉模型会收到什么数据：考生信息、匹配院校列表、历年分数线、趋势分析。让模型提前知道上下文结构。
>
> **第三层：输出约束**
> - **格式约束**：要求返回固定 JSON schema（recommendations / analysis / plan_suggestion / pros / cons）
> - **规则约束**：嵌入业务逻辑——预估分比复试线高 15+ = 保底、差值 ±15 = 稳妥、低 15+ = 冲刺
> - **数量约束**：至少 2 条、最多 6 条推荐，覆盖不同风险等级
> - **领域规则**：考虑考试科目匹配（考数二的不能推荐要求数一的专业）、保护一志愿、不歧视双非等
>
> 这种设计等价于"人工 RAG + 规则引擎"——数据和业务规则直接注入 prompt，模型只是推理和格式化引擎。

**为什么不用 Function Calling / Tool Calling？**
- 当前阶段数据量不大，直接塞 prompt 更简单
- 模式化程度高（推荐逻辑固定），不需要模型自主决策调什么工具
- 省去工具定义和解析的成本
- 后续如果数据量增大（比如想实时查询最新分数线），会考虑加 Tool Calling

---

### Q2: 你项目的 User Prompt 怎么拼的？

**实际代码逻辑：**

> User Prompt 分成 4 个 JSON 块：
>
> ```python
> user_prompt = f"""
> ## 考生信息
> {json.dumps(profile, ensure_ascii=False)}
>
> ## 匹配院校（最多15所）
> {json.dumps(schools, ensure_ascii=False)}
>
> ## 历年分数线（最近30条）
> {json.dumps(score_data, ensure_ascii=False)}
>
> ## 趋势分析（最近10条）
> {json.dumps(trends, ensure_ascii=False)}
>
> 请基于以上数据给出择校推荐。
> """
> ```
>
> 这就是手动 RAG——把检索结果直接拼接进 prompt。模型在 3000 token 的上下文窗口内，同时看到用户信息和数据，做出推理。

**为什么要`ensure_ascii=False`？**
- 默认 `ensure_ascii=True` 会把中文转成 `\uXXXX` 编码
- 对 LLM 来说，`河北` 和 "河北" 语义完全不同——Unicode 转义序列对分词器不友好
- 所以必须用 `ensure_ascii=False` 让中文字符原样输出到 prompt 里

---

### Q3: JSON 返回格式不稳定怎么办——LLM 有时返回的不是合法 JSON？

**项目中的实际处理：**

```python
def _extract_json(content: str) -> dict | None:
    # 尝试 1: 直接解析整个内容
    try:
        return json.loads(content)
    except: pass

    # 尝试 2: 找最后一个 '{'，从那里开始解析
    last_open = content.rfind('{')
    if last_open >= 0:
        try:
            return json.loads(content[last_open:])
        except: pass

    # 尝试 3: 正则匹配第一个 {...} 块
    match = re.search(r"\{[\s\S]*\}", content)
    if match:
        try:
            return json.loads(match.group())
        except: pass

    # 都失败了就返回 None，上层兜底把原文当纯文本展示
    return None
```

**面试可以补充的解法：**
- **Jsonformer / Outlines**：在生成过程中强制约束输出符合 JSON Schema，不会出现格式错误
- **Guided Generation**：部分推理框架支持限制每一步生成的 token 必须符合给定的语法
- **重试 + 错误信息反馈**：解析失败时把错误信息发回模型让它修正
- **OpenAI Structured Outputs**：OpenAI 2024 年推出的功能，100% 保证输出符合给定 JSON Schema

---

## 4. 向量数据库与 RAG

### Q1: RAG 是什么？为什么要用 RAG？

**面试标准回答：**

> RAG（Retrieval-Augmented Generation，检索增强生成）解决 LLM 的两个核心缺陷：
>
> 1. **知识截止日期**：模型训练数据有截止日期（DeepSeek-v3 约 2024 年 7 月），不知道最新的分数线、招生政策
> 2. **幻觉问题**：模型会"编造"它不知道的信息，看起来像真的但实际不存在
>
> RAG 做法：在发 prompt 给 LLM 之前，先从外部知识库检索相关信息，拼到 prompt 里。这样 LLM 就能"看到"它本来不知道的事实，输出更准确。
>
> 我的项目里：将 45 万条院校专业数据向量化存入 ChromaDB，用户提问时检索 Top-K 最相关数据，注入 prompt。

**RAG 流程（两阶段）：**

```
离线阶段（入库）:
  数据库中的文档 → Embedding 模型 → 向量 → ChromaDB

在线阶段（检索）:
  用户问题 → Embedding 模型 → 查询向量 → ChromaDB 相似度搜索 → Top-K 文档
  → 拼入 Prompt → 发给 LLM → 生成回答
```

---

### Q2: Embedding 是什么？向量检索为什么比关键词匹配好？

**面试标准回答：**

> Embedding 是把文本映射到高维向量空间的过程。语义相似的文本，向量在空间里距离近。
>
> 关键词匹配的问题：
> - 搜"计算机"找不到"软件工程"（词不匹配但意思相关）
> - 搜"AI"找不到"人工智能"（缩写 vs 全称）
> - 搜"机器学习"找不到"深度学习"（上下位关系）
>
> 向量检索引入了语义理解：
> ```
> "计算机科学"  → [0.12, -0.34, 0.56, ...]
> "软件工程"    → [0.15, -0.31, 0.52, ...]  ← 向量很接近！
> "临床医学"    → [-0.78, 0.23, -0.45, ...] ← 向量很远
> ```
>
> 所以在向量空间里，"软件工程"紧挨着"计算机科学"，跨关键词也能召回。

**相似度计算方式：**
- **余弦相似度（Cosine Similarity）**：`cos(A,B) = (A·B) / (|A|×|B|)`，范围 [-1, 1]，1 表示完全相同
- 你项目里用的欧氏距离转换：`relevance = 1.0 - min(distance, 1.0)`

---

### Q3: 你用的什么 Embedding 模型？为什么选它？

**面试标准回答：**

> 我用的是 ChromaDB 内置的 `DefaultEmbeddingFunction`，底层是 **all-MiniLM-L6-v2**：
> - 基于 ONNX Runtime 运行，无需额外安装深度学习框架
> - 输出 384 维向量
> - 模型大小约 79MB，首次使用自动从 HuggingFace 下载
> - 完全本地运行，无需 API 费用
>
> 优点是轻量零成本；缺点是它是英文模型，对中文语义匹配效果打折，长文本理解能力不如更大的模型。

**改进方向（面试加分点）：**
> 后续计划换成中文优化的 Embedding 模型，例如：
> - **BGE-large-zh-v1.5**（BAAI 开源，1024 维，中文效果 SOTA）
> - **text2vec-large-chinese**（中文语义匹配专用）
> - **m3e-base**（Moka 社区开源，中文 Embedding 基准）

---

### Q4: 长文本如何处理？Embedding 模型有输入长度限制？

**面试标准回答：**

> all-MiniLM-L6-v2 最大输入约 256 tokens。长文档不能直接整体 Embedding。
>
> **我项目的做法（硬截断）：**
> ```python
> f"{name} {province} {city} {description}"[:500]  # 超500字符直接砍掉
> ```
> 简单但会丢失信息。
>
> **更完善的方案——滑动窗口分块（Sliding Window Chunking）：**
> ```
> 原文档: [========== 1000 tokens ==========]
>
> Chunk 1: [=== 200 tokens ===]
> Chunk 2:       [=== 200 tokens ===]  ← 与 Chunk 1 重叠 50 tokens
> Chunk 3:             [=== 200 tokens ===]
> ...
> ```
> - 每个 chunk 独立 Embedding，存为独立向量
> - ID 格式：`doc_123_chunk_0`、`doc_123_chunk_1`
> - 检索时返回 Top-K 个 chunk，按 doc_id 聚合去重
> - 重叠避免关键信息刚好在切分点被切断
>
> **进阶：结合重排序（Re-ranker）**
> - 第一阶段：向量检索召回 Top-20 候选 chunk（速度快）
> - 第二阶段：Cross-encoder 对候选 chunk 精细打分重排序（精度高）
> - 最终取 Top-5 注入 prompt

---

### Q5: ChromaDB 在你的项目里具体怎么用的？

**实际代码解析：**

```python
# 1. 客户端初始化（本地持久化）
_chroma_client = chromadb.PersistentClient(
    path="./chroma_data",   # 向量数据存到本地文件
)

# 2. 创建两个 Collection（逻辑分组）
get_or_create_collection("schools")   # 院校向量
get_or_create_collection("majors")    # 专业向量

# 3. 入库（每个学校一条记录）
col.upsert(
    ids=["school_1", "school_2", ...],
    documents=[
        "河北工程大学 河北 邯郸 省属重点大学...",
        "燕山大学 河北 秦皇岛 省部共建...",
    ],
    metadatas=[
        {"school_id": 1, "name": "河北工程大学", "province": "河北", "level": "普本"},
        {"school_id": 2, "name": "燕山大学", "province": "河北", "level": "双一流"},
    ],
)

# 4. 检索
results = col.query(
    query_texts=["我想在河北读计算机"],  # 用户问题
    n_results=10,                         # 返回 Top-10
)
# → 返回语义最接近的 10 所学校
```

**关键概念：**
- **Collection**：ChromaDB 的数据容器，类似关系数据库里的 Table
- **Document**：要索引的文本，会被自动 Embedding
- **Metadata**：附加的结构化信息，不参与向量检索，但检索后可以返回
- **Distance**：表示向量之间的距离，越小越相似

---

## 5. AI Agent 多代理编排

### Q1: 什么是 AI Agent？

**面试标准回答：**

> AI Agent = LLM + 任务定义 + 外部工具/数据
>
> 跟普通 LLM 调用的区别：
> - 普通 LLM：你问它答，一问一答
> - Agent：给它一个目标，它能自己拆解步骤、调用工具、多轮推理
>
> 三个核心能力：
> 1. **规划（Planning）**：把大任务拆成小步骤
> 2. **工具使用（Tool Use）**：调用外部 API、查数据库、搜索
> 3. **记忆（Memory）**：记住上下文和历史操作

---

### Q2: 你项目里的两阶段 Agent 架构是怎样的？

**面试标准回答：**

```
                   ┌─────────────────────┐
                   │   用户发起对话       │
                   └─────────┬───────────┘
                             │
                             ▼
                   ┌─────────────────────┐
                   │  NeedsAnalysisAgent │  ← 阶段一：需求采集
                   │  • 多轮对话         │
                   │  • 了解偏好         │
                   │  • 提取权重 JSON    │
                   └─────────┬───────────┘
                             │ 权重 + 偏好
                             ▼
         ┌───────────────────────────────────┐
         │         DecisionService           │
         │  • 根据权重过滤院校               │
         │  • 查询分数线 + 趋势              │
         │  • 匹配考试科目                   │
         └───────────────┬───────────────────┘
                         │ 结构化数据
                         ▼
         ┌───────────────────────────────────┐
         │      OrchestratorAgent            │  ← 阶段二：决策推荐
         │  • 拼接 Prompt                    │
         │  • LLM 推理排序                   │
         │  • 输出推荐 JSON                  │
         └───────────────┬───────────────────┘
                         │
                         ▼
         ┌───────────────────────────────────┐
         │    前端渲染推荐卡片               │
         └───────────────────────────────────┘
```

**两个 Agent 各司其职：**

| | NeedsAnalysisAgent | OrchestratorAgent |
|---|---|---|
| **角色** | 考研顾问（对话式） | 数据决策引擎（分析式） |
| **输入** | 用户的自然语言回复 | 用户画像 JSON + 院校数据 |
| **输出** | 对话文字 + 权重 JSON | 结构化推荐 JSON |
| **轮次** | 多轮对话 | 单次请求 |
| **temperature** | 0.7（对话需要自然） | 0.4（推荐需要稳定） |

---

### Q3: 跟 LangChain / LangGraph 的区别？为什么不用它们？

**对比表：**

| | 我的项目 | LangChain | LangGraph |
|---|---|---|---|
| **实现方式** | 手写 Python + OpenAI SDK | 预置 Chain/Agent 抽象 | 状态图（StateGraph） |
| **Agent 定义** | System Prompt + API 调用 | AgentExecutor + Tool | 节点（Node）+ 边（Edge） |
| **Prompt 管理** | 字符串常量 | PromptTemplate / Hub | 节点内置 |
| **多 Agent 协作** | 手动串联：A 输出 → B 输入 | SequentialChain | 条件边 + 状态传递 |
| **工具调用** | 数据写进 prompt | Tool / ToolCall | ToolNode |
| **学习曲线** | 低，纯 Python | 中，理解 Chain 概念 | 高，理解图/状态/条件边 |
| **灵活性** | 完全可控 | 框架提供便利但有约束 | 灵活但代码量大 |
| **适用场景** | 简单线性流水线（≤3 步） | 中等复杂度 | 多步分支循环嵌套 |

**面试可以这样兜：**

> 我场景是线性流水线——需求采集完了自动到推荐，没有复杂分支、循环、条件判断。手写 Agent 代码清晰，引入 LangChain/LangGraph 反而多一层抽象。
>
> LangChain 的问题：版本迭代快 API 不稳定、抽象太多排查困难、文档落后于代码。Andrew Ng 说过"LangChain is great for demos, painful for production"。
>
> LangGraph 更适合的场景：需要循环（Agent 调用工具 → 看结果 → 决定是否再调）、条件分支（根据中间结果选不同路径）、Human-in-the-loop（某个步骤需要人工审核才能继续）。
>
> 后续如果要给 Agent 加 Tool Calling（让它自己决定什么时候查数据库、什么时候调计算器），会考虑切到 LangGraph 的 StateGraph + ToolNode。

---

### Q4: 如果要给 Agent 加 Tool Calling，怎么做？

**概念解释：**

> Tool Calling（函数调用）让 LLM 能自主决定"我现在需要调什么函数/查什么数据"：
>
> ```
> 用户："帮我分析清华计算机今年的难度"
>
> Agent 思考 → "我需要查清华大学计算机专业的分数线"
> Agent 动作 → 调用 tool_get_score_lines("清华大学", "计算机")
> Tool 返回 → {"2024": 375, "2025": 382, "trend": "上升"}
> Agent 思考 → "分数线在涨，难度在增加"
> Agent 回答 → "清华计算机近两年复试线从375涨到382，呈上升趋势，建议..."
> ```
>
> 实现方式（LangGraph）：
> ```python
> from langgraph.graph import StateGraph
> from langgraph.prebuilt import ToolNode
>
> # 定义工具
> tools = [search_schools, get_score_lines, calculate_risk]
>
> # 定义图
> graph = StateGraph(AgentState)
> graph.add_node("agent", agent_node)        # LLM 推理
> graph.add_node("tools", ToolNode(tools))   # 工具执行
> graph.add_conditional_edges(
>     "agent",
>     should_call_tools,  # 判断是否需要调工具
>     {"tools": "tools", "end": END}
> )
> graph.add_edge("tools", "agent")  # 工具结果返回 Agent 继续推理
> ```

---

## 附录：面试套路总结

### 被问到不会的问题怎么答

1. **不要直接说"不会"**，改成"目前还没深入这个方向，但我的理解是..."
2. **把自己会的引过来**："虽然没用 LangGraph，但我手写了两阶段 Agent，核心思路跟 StateGraph 类似..."
3. **展示学习意愿**："后续计划补上这块，已经在看相关文档和论文"

### 被追问项目缺陷怎么兜

> "目前方案对数据做了硬截断，对齐 MiniLM 的输入限制。后续计划切到 BGE-large-zh 中文 Embedding + 滑动窗口分块 + Cross-encoder 重排序，提高中文语义匹配精度和召回率。"

### 面试官想看到的

- 不是完美的代码，而是 **你清楚自己代码的边界和局限**
- 不是背框架 API，而是 **理解底层原理**
- 不是"我用过 X"，而是 **"我为什么选 X 不选 Y，X 解决了什么问题"**
