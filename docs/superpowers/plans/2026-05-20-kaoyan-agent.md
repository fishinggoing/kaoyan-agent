# 考研择校 Agent PoC 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一个命令行考研择校 Agent PoC，通过多轮对话引导学生完成择校决策。

**Architecture:** 单一 Python 包，SQLite 存储学校数据，Anthropic SDK 驱动对话 Agent 的 Function Calling 循环。数据采集 Agent 留骨架，PoC 用手工种子数据。

**Tech Stack:** Python 3.12+, Anthropic SDK, SQLite, pytest

---

## 文件结构

```
kaoyan_agent/
├── __init__.py
├── cli.py                # CLI 入口 + 主循环
├── db/
│   ├── __init__.py
│   ├── schema.py         # 建表语句
│   └── queries.py        # 查询函数（Agent 调用的工具实现）
├── agent/
│   ├── __init__.py
│   ├── dialogue.py       # 对话 Agent 核心循环
│   ├── tools.py          # Anthropic Function Calling 工具定义
│   └── prompts.py        # 系统提示词
├── collector/
│   ├── __init__.py
│   └── __init__.py       # 骨架（PoC 不实现）
└── seed_data.py          # 手工种子数据（5-10 所学校）
tests/
├── __init__.py
├── test_schema.py
├── test_queries.py
└── test_dialogue.py
```

---

### Task 1: 项目初始化

**Files:**
- Create: `kaoyan_agent/__init__.py`
- Create: `kaoyan_agent/db/__init__.py`
- Create: `kaoyan_agent/agent/__init__.py`
- Create: `kaoyan_agent/collector/__init__.py`
- Create: `requirements.txt`
- Create: `.gitignore`
- Create: `tests/__init__.py`

- [ ] **Step 1: 创建目录结构和空 __init__.py**

```bash
mkdir -p kaoyan_agent/db kaoyan_agent/agent kaoyan_agent/collector tests
touch kaoyan_agent/__init__.py kaoyan_agent/db/__init__.py kaoyan_agent/agent/__init__.py kaoyan_agent/collector/__init__.py tests/__init__.py
```

- [ ] **Step 2: 编写 requirements.txt**

```txt
anthropic>=0.39.0
pytest>=8.0.0
```

- [ ] **Step 3: 编写 .gitignore**

```gitignore
__pycache__/
*.pyc
*.db
.env
.superpowers/
venv/
.venv/
```

- [ ] **Step 4: 创建虚拟环境并安装依赖**

```bash
python -m venv venv
source venv/Scripts/activate  # Windows Git Bash
pip install -r requirements.txt
```

- [ ] **Step 5: 验证**

```bash
python -c "import anthropic; print(anthropic.__version__)"
```

Expected: 输出 anthropic 版本号

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "chore: init project structure and dependencies"
```

---

### Task 2: 数据库 Schema

**Files:**
- Create: `kaoyan_agent/db/schema.py`
- Create: `tests/test_schema.py`

- [ ] **Step 1: 编写测试 — 验证表创建**

```python
# tests/test_schema.py
import sqlite3
import pytest
from kaoyan_agent.db.schema import create_tables


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    create_tables(conn)
    yield conn
    conn.close()


def test_schools_table_exists(db):
    cursor = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='schools'")
    assert cursor.fetchone() is not None


def test_schools_columns(db):
    db.execute("""
        INSERT INTO schools (name, tier, province, city, type, website)
        VALUES ('北京大学', '985', '北京', '北京', '综合', 'https://example.com')
    """)
    row = db.execute("SELECT * FROM schools WHERE name='北京大学'").fetchone()
    assert row['tier'] == '985'
    assert row['province'] == '北京'


def test_majors_table_exists(db):
    cursor = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='majors'")
    assert cursor.fetchone() is not None


def test_admission_scores_table_exists(db):
    cursor = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='admission_scores'")
    assert cursor.fetchone() is not None


def test_admitted_scores_table_exists(db):
    cursor = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='admitted_scores'")
    assert cursor.fetchone() is not None


def test_employment_quality_table_exists(db):
    cursor = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='employment_quality'")
    assert cursor.fetchone() is not None


def test_foreign_key_major_to_school(db):
    db.execute("INSERT INTO schools (name, tier, province, city, type) VALUES ('清华', '985', '北京', '北京', '综合')")
    school_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    db.execute(
        "INSERT INTO majors (school_id, name, discipline_rank, exam_subjects) VALUES (?, ?, ?, ?)",
        (school_id, '计算机科学', 'A+', '["政治","英语","数学一","408"]')
    )
    row = db.execute("SELECT * FROM majors WHERE school_id=?", (school_id,)).fetchone()
    assert row['name'] == '计算机科学'
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/test_schema.py -v
```

Expected: FAIL (ModuleNotFoundError)

- [ ] **Step 3: 编写 schema.py**

```python
# kaoyan_agent/db/schema.py
import sqlite3


def create_tables(conn: sqlite3.Connection):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS schools (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name VARCHAR(128) NOT NULL,
            tier VARCHAR(32) NOT NULL DEFAULT '',
            province VARCHAR(32) NOT NULL DEFAULT '',
            city VARCHAR(32) NOT NULL DEFAULT '',
            type VARCHAR(32) NOT NULL DEFAULT '',
            website VARCHAR(256) NOT NULL DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS majors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            school_id INTEGER NOT NULL REFERENCES schools(id),
            name VARCHAR(128) NOT NULL,
            discipline_rank VARCHAR(8) NOT NULL DEFAULT '',
            exam_subjects TEXT NOT NULL DEFAULT '[]'
        );

        CREATE TABLE IF NOT EXISTS admission_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            major_id INTEGER NOT NULL REFERENCES majors(id),
            year INTEGER NOT NULL,
            admission_line INTEGER,
            applicants INTEGER,
            enrolled INTEGER,
            push_free_ratio REAL
        );

        CREATE TABLE IF NOT EXISTS admitted_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            major_id INTEGER NOT NULL REFERENCES majors(id),
            year INTEGER NOT NULL,
            lowest_score INTEGER,
            avg_score INTEGER,
            highest_score INTEGER
        );

        CREATE TABLE IF NOT EXISTS employment_quality (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            school_id INTEGER NOT NULL REFERENCES schools(id),
            year INTEGER NOT NULL,
            employment_rate REAL,
            avg_salary INTEGER,
            summary TEXT NOT NULL DEFAULT ''
        );
    """)
    conn.commit()
```

- [ ] **Step 4: 运行测试确认通过**

```bash
pytest tests/test_schema.py -v
```

Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add kaoyan_agent/db/schema.py tests/test_schema.py
git commit -m "feat: add database schema (5 tables)"
```

---

### Task 3: 查询函数

**Files:**
- Create: `kaoyan_agent/db/queries.py`
- Create: `tests/test_queries.py`

- [ ] **Step 1: 编写测试**

```python
# tests/test_queries.py
import sqlite3
import pytest
from kaoyan_agent.db.schema import create_tables
from kaoyan_agent.db.queries import (
    search_schools,
    get_majors,
    query_scores,
    get_employment,
    compare_schools,
)


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    create_tables(conn)
    _seed(conn)
    yield conn
    conn.close()


def _seed(conn):
    conn.execute(
        "INSERT INTO schools (name, tier, province, city, type) VALUES (?,?,?,?,?)",
        ("浙江大学", "985", "浙江", "杭州", "综合"),
    )
    conn.execute(
        "INSERT INTO schools (name, tier, province, city, type) VALUES (?,?,?,?,?)",
        ("南京大学", "985", "江苏", "南京", "综合"),
    )
    conn.execute(
        "INSERT INTO schools (name, tier, province, city, type) VALUES (?,?,?,?,?)",
        ("杭州电子科技大学", "双非", "浙江", "杭州", "理工"),
    )
    zju = conn.execute("SELECT id FROM schools WHERE name='浙江大学'").fetchone()[0]
    nju = conn.execute("SELECT id FROM schools WHERE name='南京大学'").fetchone()[0]
    hdu = conn.execute("SELECT id FROM schools WHERE name='杭州电子科技大学'").fetchone()[0]

    conn.execute(
        "INSERT INTO majors (school_id, name, discipline_rank, exam_subjects) VALUES (?,?,?,?)",
        (zju, "计算机科学与技术", "A+", '["政治","英语","数学一","408"]'),
    )
    conn.execute(
        "INSERT INTO majors (school_id, name, discipline_rank, exam_subjects) VALUES (?,?,?,?)",
        (nju, "计算机科学与技术", "A", '["政治","英语","数学一","408"]'),
    )
    conn.execute(
        "INSERT INTO majors (school_id, name, discipline_rank, exam_subjects) VALUES (?,?,?,?)",
        (hdu, "计算机科学与技术", "B+", '["政治","英语","数学一","408"]'),
    )
    conn.execute(
        "INSERT INTO majors (school_id, name, discipline_rank, exam_subjects) VALUES (?,?,?,?)",
        (zju, "软件工程", "A+", '["政治","英语","数学一","878"]'),
    )

    zju_cs = conn.execute(
        "SELECT id FROM majors WHERE school_id=? AND name='计算机科学与技术'", (zju,)
    ).fetchone()[0]
    nju_cs = conn.execute(
        "SELECT id FROM majors WHERE school_id=? AND name='计算机科学与技术'", (nju,)
    ).fetchone()[0]
    hdu_cs = conn.execute(
        "SELECT id FROM majors WHERE school_id=? AND name='计算机科学与技术'", (hdu,)
    ).fetchone()[0]

    conn.execute(
        "INSERT INTO admission_scores (major_id, year, admission_line, applicants, enrolled, push_free_ratio) VALUES (?,?,?,?,?,?)",
        (zju_cs, 2025, 380, 1200, 45, 0.6),
    )
    conn.execute(
        "INSERT INTO admission_scores (major_id, year, admission_line, applicants, enrolled, push_free_ratio) VALUES (?,?,?,?,?,?)",
        (nju_cs, 2025, 370, 900, 50, 0.55),
    )
    conn.execute(
        "INSERT INTO admission_scores (major_id, year, admission_line, applicants, enrolled, push_free_ratio) VALUES (?,?,?,?,?,?)",
        (hdu_cs, 2025, 310, 600, 80, 0.2),
    )

    conn.execute(
        "INSERT INTO employment_quality (school_id, year, employment_rate, avg_salary, summary) VALUES (?,?,?,?,?)",
        (zju, 2024, 0.98, 250000, "浙江大学计算机就业集中在杭州互联网企业"),
    )
    conn.execute(
        "INSERT INTO employment_quality (school_id, year, employment_rate, avg_salary, summary) VALUES (?,?,?,?,?)",
        (nju, 2024, 0.97, 260000, "南京大学毕业生多去上海/南京"),
    )
    conn.commit()


def test_search_schools_by_province(db):
    results = search_schools(db, province="浙江")
    names = [r["name"] for r in results]
    assert "浙江大学" in names
    assert "杭州电子科技大学" in names
    assert "南京大学" not in names


def test_search_schools_by_tier(db):
    results = search_schools(db, tier="985")
    names = [r["name"] for r in results]
    assert "浙江大学" in names
    assert "南京大学" in names
    assert len(names) == 2


def test_search_schools_combined(db):
    results = search_schools(db, province="浙江", tier="985")
    names = [r["name"] for r in results]
    assert names == ["浙江大学"]


def test_get_majors(db):
    zju = db.execute("SELECT id FROM schools WHERE name='浙江大学'").fetchone()[0]
    results = get_majors(db, school_id=zju)
    names = [r["name"] for r in results]
    assert "计算机科学与技术" in names
    assert "软件工程" in names


def test_query_scores(db):
    zju = db.execute("SELECT id FROM schools WHERE name='浙江大学'").fetchone()[0]
    zju_cs = db.execute(
        "SELECT id FROM majors WHERE school_id=? AND name='计算机科学与技术'", (zju,)
    ).fetchone()[0]
    results = query_scores(db, major_id=zju_cs)
    latest = results[0]
    assert latest["admission_line"] == 380
    assert latest["applicants"] == 1200


def test_get_employment(db):
    zju = db.execute("SELECT id FROM schools WHERE name='浙江大学'").fetchone()[0]
    results = get_employment(db, school_id=zju)
    assert len(results) > 0
    assert results[0]["employment_rate"] == 0.98


def test_compare_schools(db):
    zju = db.execute("SELECT id FROM schools WHERE name='浙江大学'").fetchone()[0]
    nju = db.execute("SELECT id FROM schools WHERE name='南京大学'").fetchone()[0]
    results = compare_schools(db, [zju, nju], "计算机科学与技术")
    assert len(results) == 2
    assert results[0]["school_name"] == "浙江大学"
    assert results[1]["school_name"] == "南京大学"
    assert results[0]["tier"] == "985"
    assert "admission_line" in results[0].keys()
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/test_queries.py -v
```

Expected: FAIL (ModuleNotFoundError for queries)

- [ ] **Step 3: 编写 queries.py**

```python
# kaoyan_agent/db/queries.py
import sqlite3
from typing import Optional


def search_schools(
    conn: sqlite3.Connection,
    province: Optional[str] = None,
    tier: Optional[str] = None,
    type: Optional[str] = None,
    keyword: Optional[str] = None,
) -> list[dict]:
    query = "SELECT * FROM schools WHERE 1=1"
    params = []
    if province:
        query += " AND province = ?"
        params.append(province)
    if tier:
        query += " AND tier = ?"
        params.append(tier)
    if type:
        query += " AND type = ?"
        params.append(type)
    if keyword:
        query += " AND name LIKE ?"
        params.append(f"%{keyword}%")
    cursor = conn.execute(query, params)
    return [dict(row) for row in cursor.fetchall()]


def get_majors(
    conn: sqlite3.Connection,
    school_id: Optional[int] = None,
    discipline: Optional[str] = None,
) -> list[dict]:
    query = """
        SELECT m.*, s.name as school_name
        FROM majors m JOIN schools s ON m.school_id = s.id
        WHERE 1=1
    """
    params = []
    if school_id:
        query += " AND m.school_id = ?"
        params.append(school_id)
    if discipline:
        query += " AND m.name LIKE ?"
        params.append(f"%{discipline}%")
    cursor = conn.execute(query, params)
    return [dict(row) for row in cursor.fetchall()]


def query_scores(
    conn: sqlite3.Connection,
    major_id: Optional[int] = None,
    year: Optional[int] = None,
) -> list[dict]:
    query = """
        SELECT a.*, m.name as major_name, s.name as school_name
        FROM admission_scores a
        JOIN majors m ON a.major_id = m.id
        JOIN schools s ON m.school_id = s.id
        WHERE 1=1
    """
    params = []
    if major_id:
        query += " AND a.major_id = ?"
        params.append(major_id)
    if year:
        query += " AND a.year = ?"
        params.append(year)
    query += " ORDER BY a.year DESC"
    cursor = conn.execute(query, params)
    return [dict(row) for row in cursor.fetchall()]


def query_admitted_scores(
    conn: sqlite3.Connection,
    major_id: Optional[int] = None,
    year: Optional[int] = None,
) -> list[dict]:
    query = """
        SELECT a.*, m.name as major_name, s.name as school_name
        FROM admitted_scores a
        JOIN majors m ON a.major_id = m.id
        JOIN schools s ON m.school_id = s.id
        WHERE 1=1
    """
    params = []
    if major_id:
        query += " AND a.major_id = ?"
        params.append(major_id)
    if year:
        query += " AND a.year = ?"
        params.append(year)
    query += " ORDER BY a.year DESC"
    cursor = conn.execute(query, params)
    return [dict(row) for row in cursor.fetchall()]


def get_employment(
    conn: sqlite3.Connection,
    school_id: Optional[int] = None,
) -> list[dict]:
    query = """
        SELECT e.*, s.name as school_name
        FROM employment_quality e
        JOIN schools s ON e.school_id = s.id
        WHERE 1=1
    """
    params = []
    if school_id:
        query += " AND e.school_id = ?"
        params.append(school_id)
    query += " ORDER BY e.year DESC"
    cursor = conn.execute(query, params)
    return [dict(row) for row in cursor.fetchall()]


def compare_schools(
    conn: sqlite3.Connection,
    school_ids: list[int],
    major_name: str,
) -> list[dict]:
    placeholders = ",".join("?" for _ in school_ids)
    query = f"""
        SELECT s.id as school_id, s.name as school_name, s.tier, s.province, s.city,
               m.name as major_name, m.discipline_rank,
               a.year, a.admission_line, a.applicants, a.enrolled, a.push_free_ratio
        FROM schools s
        JOIN majors m ON m.school_id = s.id
        LEFT JOIN admission_scores a ON a.major_id = m.id
        WHERE s.id IN ({placeholders})
          AND m.name = ?
        ORDER BY s.id, a.year DESC
    """
    params = [*school_ids, major_name]
    cursor = conn.execute(query, params)
    rows = cursor.fetchall()

    seen = {}
    result = []
    for row in rows:
        sid = row["school_id"]
        if sid not in seen:
            seen[sid] = dict(row)
            result.append(seen[sid])
    return result
```

- [ ] **Step 4: 运行测试确认通过**

```bash
pytest tests/test_queries.py -v
```

Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add kaoyan_agent/db/queries.py tests/test_queries.py
git commit -m "feat: add query functions (6 tools)"
```

---

### Task 4: Agent 工具定义

**Files:**
- Create: `kaoyan_agent/agent/tools.py`

- [ ] **Step 1: 编写工具定义**

```python
# kaoyan_agent/agent/tools.py

TOOLS = [
    {
        "name": "search_schools",
        "description": "按条件搜索学校。可以按省份、学校层次、类型和关键词筛选。",
        "input_schema": {
            "type": "object",
            "properties": {
                "province": {
                    "type": "string",
                    "description": "省份名称，如'浙江'、'江苏'",
                },
                "tier": {
                    "type": "string",
                    "enum": ["985", "211", "双一流", "双非"],
                    "description": "学校层次",
                },
                "type": {
                    "type": "string",
                    "description": "学校类型，如'综合'、'理工'、'师范'",
                },
                "keyword": {
                    "type": "string",
                    "description": "学校名称关键词",
                },
            },
        },
    },
    {
        "name": "get_majors",
        "description": "查询学校开设的专业及学科评估等级。",
        "input_schema": {
            "type": "object",
            "properties": {
                "school_id": {
                    "type": "integer",
                    "description": "学校ID，从search_schools结果中获取",
                },
                "discipline": {
                    "type": "string",
                    "description": "专业名称关键词，如'计算机'、'软件'",
                },
            },
        },
    },
    {
        "name": "query_scores",
        "description": "查询复试分数线、报录比、招生人数等硬指标。返回最新年份数据优先。",
        "input_schema": {
            "type": "object",
            "properties": {
                "major_id": {
                    "type": "integer",
                    "description": "专业ID，从get_majors结果中获取",
                },
                "year": {
                    "type": "integer",
                    "description": "查询年份，不填则返回所有年份",
                },
            },
        },
    },
    {
        "name": "query_admitted_scores",
        "description": "查询实际录取分数（最低分/平均分/最高分）。仅在用户明确询问'实际录取分数'、'录取的人考了多少分'时才调用此工具。",
        "input_schema": {
            "type": "object",
            "properties": {
                "major_id": {
                    "type": "integer",
                    "description": "专业ID",
                },
                "year": {
                    "type": "integer",
                    "description": "查询年份",
                },
            },
        },
    },
    {
        "name": "get_employment",
        "description": "查询学校的就业质量信息（就业率、平均薪资、就业去向摘要）。",
        "input_schema": {
            "type": "object",
            "properties": {
                "school_id": {
                    "type": "integer",
                    "description": "学校ID",
                },
            },
        },
    },
    {
        "name": "compare_schools",
        "description": "横向对比多所学校同一专业的硬指标。输入学校ID列表和专业名称，返回各校分数线、报录比、学科评估等数据。",
        "input_schema": {
            "type": "object",
            "properties": {
                "school_ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "要对比的学校ID列表",
                },
                "major_name": {
                    "type": "string",
                    "description": "专业名称",
                },
            },
            "required": ["school_ids", "major_name"],
        },
    },
]
```

- [ ] **Step 2: 验证 JSON 格式合法**

```bash
python -c "from kaoyan_agent.agent.tools import TOOLS; import json; [json.dumps(t) for t in TOOLS]; print('OK')"
```

Expected: OK

- [ ] **Step 3: Commit**

```bash
git add kaoyan_agent/agent/tools.py
git commit -m "feat: add agent tool definitions (6 tools)"
```

---

### Task 5: 系统提示词

**Files:**
- Create: `kaoyan_agent/agent/prompts.py`

- [ ] **Step 1: 编写提示词**

```python
# kaoyan_agent/agent/prompts.py

SYSTEM_PROMPT = """你是一个考研择校顾问。你的任务是通过多轮对话帮助学生找到适合的学校和专业。

## 交互模式判断

根据学生的问题自动判断属于哪种模式：

**模式一：信息咨询**（学生问具体学校/专业的信息）
- 策略：先给硬指标（分数线、报录比、招生人数等），再给软信息（学校层次、学科评估、就业等），最后提出你的看法
- 不需要追问学生偏好

**模式二：择校决策**（学生需要推荐或做选择）
- 策略：不要急于给结论！先了解学生的软偏好，重点确认地理位置意愿
- 流程：了解基本情况 → 深挖地理位置偏好 → 确认学校层次/专业方向 → 数据查询 → 给出推荐

## 行为准则

1. 择校决策时，至少确认地理位置偏好后才给出推荐
2. 硬指标（分数线、报录比）只陈述数据，不带主观评价。说"复试线350分"而不是"分数线不高"
3. 软信息（就业、学科评估）可以给出分析，但要标明这是你的判断
4. 数据有缺失或年份较旧时，直接告诉学生
5. 一次不要问太多问题，保持对话自然
6. 比较学校时，使用 compare_schools 工具做横向对比

## eventual response format

- 信息咨询：先列出硬指标数据，再补充软信息，最后给一个简短看法
- 择校决策：按"推荐学校 → 硬指标对比 → 软信息分析 → 报考建议"的结构输出"""
```

- [ ] **Step 2: 验证**

```bash
python -c "from kaoyan_agent.agent.prompts import SYSTEM_PROMPT; print(len(SYSTEM_PROMPT))"
```

Expected: 输出字符数

- [ ] **Step 3: Commit**

```bash
git add kaoyan_agent/agent/prompts.py
git commit -m "feat: add system prompt for dialogue agent"
```

---

### Task 6: 对话 Agent 核心循环

**Files:**
- Create: `kaoyan_agent/agent/dialogue.py`
- Create: `tests/test_dialogue.py`

- [ ] **Step 1: 编写测试**

```python
# tests/test_dialogue.py
import sqlite3
import json
from unittest.mock import patch, MagicMock
from kaoyan_agent.db.schema import create_tables
from kaoyan_agent.agent.dialogue import execute_tool, run_agent


def test_execute_tool_search_schools():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    create_tables(conn)
    conn.execute(
        "INSERT INTO schools (name, tier, province, city) VALUES (?,?,?,?)",
        ("浙江大学", "985", "浙江", "杭州"),
    )
    conn.commit()

    result = execute_tool(conn, "search_schools", {"province": "浙江"})
    data = json.loads(result)
    assert len(data) == 1
    assert data[0]["name"] == "浙江大学"


def test_execute_tool_unknown():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    result = execute_tool(conn, "nonexistent", {})
    assert "error" in result.lower()


def test_run_agent_returns_structure():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    create_tables(conn)

    from kaoyan_agent.agent.dialogue import execute_tool

    result = execute_tool(
        conn, "search_schools", {"tier": "985", "province": "浙江"}
    )
    data = json.loads(result)
    assert isinstance(data, list)
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/test_dialogue.py -v
```

Expected: FAIL

- [ ] **Step 3: 编写 dialogue.py**

```python
# kaoyan_agent/agent/dialogue.py
import json
import sqlite3
from anthropic import Anthropic
from kaoyan_agent.agent.tools import TOOLS
from kaoyan_agent.agent.prompts import SYSTEM_PROMPT
from kaoyan_agent.db import queries


def execute_tool(conn: sqlite3.Connection, tool_name: str, tool_input: dict) -> str:
    func_map = {
        "search_schools": queries.search_schools,
        "get_majors": queries.get_majors,
        "query_scores": queries.query_scores,
        "query_admitted_scores": queries.query_admitted_scores,
        "get_employment": queries.get_employment,
        "compare_schools": queries.compare_schools,
    }
    func = func_map.get(tool_name)
    if func is None:
        return json.dumps({"error": f"Unknown tool: {tool_name}"})

    result = func(conn, **tool_input)
    return json.dumps(result, ensure_ascii=False, indent=2)


def run_agent(
    client: Anthropic,
    conn: sqlite3.Connection,
    messages: list[dict],
) -> dict:
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        tools=TOOLS,
        messages=messages,
    )

    text = ""
    tool_calls = []

    for block in response.content:
        if block.type == "text":
            text += block.text
        elif block.type == "tool_use":
            tool_calls.append(
                {
                    "id": block.id,
                    "name": block.name,
                    "input": dict(block.input),
                }
            )

    return {
        "text": text,
        "tool_calls": tool_calls,
        "stop_reason": response.stop_reason,
    }
```

- [ ] **Step 4: 运行测试确认通过**

```bash
pytest tests/test_dialogue.py -v
```

Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add kaoyan_agent/agent/dialogue.py tests/test_dialogue.py
git commit -m "feat: add dialogue agent core loop"
```

---

### Task 7: CLI 入口

**Files:**
- Create: `kaoyan_agent/cli.py`

- [ ] **Step 1: 编写 CLI**

```python
# kaoyan_agent/cli.py
import os
import sqlite3
import json
from anthropic import Anthropic
from kaoyan_agent.db.schema import create_tables
from kaoyan_agent.agent.dialogue import run_agent, execute_tool


def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("请设置 ANTHROPIC_API_KEY 环境变量")
        return

    client = Anthropic(api_key=api_key)
    conn = sqlite3.connect("kaoyan.db")
    conn.row_factory = sqlite3.Row
    create_tables(conn)

    print("=" * 50)
    print("  考研择校助手")
    print("  可以问我：'帮我推荐学校' 或 '浙大计算机怎么样'")
    print("  输入 /quit 退出")
    print("=" * 50)

    messages = []
    while True:
        try:
            user_input = input("\n你: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break

        if user_input.lower() in ("/quit", "/exit", "quit", "exit"):
            print("再见！")
            break

        if not user_input:
            continue

        messages.append({"role": "user", "content": user_input})

        while True:
            result = run_agent(client, conn, messages)

            if result["text"]:
                print(f"\n助手: {result['text']}")

            if result["stop_reason"] == "end_turn":
                messages.append({"role": "assistant", "content": result["text"]})
                break

            if result["stop_reason"] == "tool_use":
                tool_content = []
                for tc in result["tool_calls"]:
                    tool_result = execute_tool(conn, tc["name"], tc["input"])
                    print(f"\n[查询: {tc['name']}]")
                    tool_content.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": tc["id"],
                            "content": tool_result,
                        }
                    )

                messages.append(
                    {
                        "role": "assistant",
                        "content": [
                            *[
                                {
                                    "type": "tool_use",
                                    "id": tc["id"],
                                    "name": tc["name"],
                                    "input": tc["input"],
                                }
                                for tc in result["tool_calls"]
                            ],
                            *(
                                [{"type": "text", "text": result["text"]}]
                                if result["text"]
                                else []
                            ),
                        ],
                    }
                )
                messages.append({"role": "user", "content": tool_content})

    conn.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 验证语法**

```bash
python -c "from kaoyan_agent.cli import main; print('OK')"
```

Expected: OK

- [ ] **Step 3: Commit**

```bash
git add kaoyan_agent/cli.py
git commit -m "feat: add CLI entry point"
```

---

### Task 8: 种子数据

**Files:**
- Create: `kaoyan_agent/seed_data.py`

- [ ] **Step 1: 编写种子数据**

```python
# kaoyan_agent/seed_data.py
import sqlite3
from kaoyan_agent.db.schema import create_tables


def seed(conn: sqlite3.Connection):
    create_tables(conn)

    schools = [
        ("北京大学", "985", "北京", "北京", "综合"),
        ("清华大学", "985", "北京", "北京", "综合"),
        ("浙江大学", "985", "浙江", "杭州", "综合"),
        ("上海交通大学", "985", "上海", "上海", "综合"),
        ("南京大学", "985", "江苏", "南京", "综合"),
        ("华中科技大学", "985", "湖北", "武汉", "理工"),
        ("武汉大学", "985", "湖北", "武汉", "综合"),
        ("杭州电子科技大学", "双非", "浙江", "杭州", "理工"),
        ("南京邮电大学", "双非", "江苏", "南京", "理工"),
        ("深圳大学", "双非", "广东", "深圳", "综合"),
    ]

    majors_data = {
        "计算机科学与技术": {
            "浙大": "A+",
            "北大": "A+",
            "清华": "A+",
            "上交": "A",
            "南大": "A",
            "华科": "A",
            "武大": "A-",
            "杭电": "B+",
            "南邮": "B",
            "深大": "B",
        },
        "软件工程": {
            "浙大": "A+",
            "北大": "A",
            "清华": "A",
            "上交": "A-",
            "南大": "A",
            "华科": "B+",
            "武大": "B+",
            "杭电": "B",
            "南邮": "B-",
            "深大": "B-",
        },
        "电子信息": {
            "浙大": "A-",
            "清华": "A+",
            "上交": "A",
            "南大": "B+",
            "华科": "B+",
            "杭电": "B+",
            "南邮": "B+",
        },
    }

    scores_data = {
        ("计算机科学与技术", "北京大学", 2025): (380, 1500, 35, 0.65),
        ("计算机科学与技术", "浙江大学", 2025): (375, 1200, 45, 0.60),
        ("计算机科学与技术", "南京大学", 2025): (370, 900, 50, 0.55),
        ("计算机科学与技术", "杭州电子科技大学", 2025): (310, 600, 80, 0.20),
        ("计算机科学与技术", "南京邮电大学", 2025): (300, 500, 90, 0.15),
        ("计算机科学与技术", "深圳大学", 2025): (320, 700, 60, 0.25),
        ("计算机科学与技术", "上海交通大学", 2025): (385, 1300, 30, 0.70),
        ("计算机科学与技术", "华中科技大学", 2025): (360, 800, 55, 0.50),
        ("计算机科学与技术", "武汉大学", 2025): (355, 750, 50, 0.50),
        ("计算机科学与技术", "清华大学", 2025): (395, 1000, 20, 0.75),
        ("软件工程", "浙江大学", 2025): (365, 600, 40, 0.55),
        ("软件工程", "南京大学", 2025): (360, 500, 45, 0.50),
        ("软件工程", "上海交通大学", 2025): (370, 550, 35, 0.60),
        ("软件工程", "华中科技大学", 2025): (345, 400, 50, 0.45),
        ("软件工程", "武汉大学", 2025): (340, 380, 48, 0.45),
        ("电子信息", "浙江大学", 2025): (355, 700, 50, 0.50),
        ("电子信息", "南京大学", 2025): (350, 500, 45, 0.45),
        ("电子信息", "上海交通大学", 2025): (365, 600, 35, 0.55),
        ("电子信息", "杭州电子科技大学", 2025): (290, 450, 100, 0.15),
        ("电子信息", "南京邮电大学", 2025): (285, 400, 90, 0.10),
        ("电子信息", "华中科技大学", 2025): (340, 450, 60, 0.40),
        ("电子信息", "清华大学", 2025): (390, 500, 25, 0.70),
    }

    employment_data = {
        "北京大学": (0.98, 280000, "北大毕业生广泛分布于各大互联网公司和金融机构"),
        "清华大学": (0.99, 300000, "清华计算机毕业生起薪极高，多进入头部企业和出国深造"),
        "浙江大学": (0.98, 250000, "浙江大学计算机就业集中在杭州互联网企业，阿里系公司为主要去向"),
        "上海交通大学": (0.97, 260000, "上交毕业生多去上海互联网/金融企业"),
        "南京大学": (0.97, 240000, "南京大学毕业生多去上海/南京互联网企业"),
        "华中科技大学": (0.95, 200000, "华科毕业生在深圳/武汉互联网企业就业率较高"),
        "武汉大学": (0.94, 190000, "武大毕业生广泛分布在中部和东部地区"),
        "杭州电子科技大学": (0.92, 150000, "杭电毕业生在杭州互联网企业认可度高，性价比好"),
        "南京邮电大学": (0.91, 140000, "南邮毕业生在通信/互联网行业就业稳定"),
        "深圳大学": (0.93, 180000, "深大毕业生在深圳互联网企业就业有地域优势"),
    }

    school_ids = {}
    for s in schools:
        conn.execute(
            "INSERT INTO schools (name, tier, province, city, type) VALUES (?,?,?,?,?)",
            s,
        )
        school_ids[s[0]] = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    major_ids = {}
    for major_name, school_ranks in majors_data.items():
        short_name_map = {
            "浙大": "浙江大学",
            "北大": "北京大学",
            "清华": "清华大学",
            "上交": "上海交通大学",
            "南大": "南京大学",
            "华科": "华中科技大学",
            "武大": "武汉大学",
            "杭电": "杭州电子科技大学",
            "南邮": "南京邮电大学",
            "深大": "深圳大学",
        }
        for short, rank in school_ranks.items():
            full_name = short_name_map[short]
            sid = school_ids[full_name]
            conn.execute(
                "INSERT INTO majors (school_id, name, discipline_rank, exam_subjects) VALUES (?,?,?,?)",
                (
                    sid,
                    major_name,
                    rank,
                    '["政治","英语","数学一","408"]',
                ),
            )
            major_ids[(major_name, full_name)] = conn.execute(
                "SELECT last_insert_rowid()"
            ).fetchone()[0]

    for (major_name, school_name, year), (
        line,
        applicants,
        enrolled,
        push_ratio,
    ) in scores_data.items():
        mid = major_ids[(major_name, school_name)]
        conn.execute(
            "INSERT INTO admission_scores (major_id, year, admission_line, applicants, enrolled, push_free_ratio) VALUES (?,?,?,?,?,?)",
            (mid, year, line, applicants, enrolled, push_ratio),
        )

    for school_name, (rate, salary, summary) in employment_data.items():
        sid = school_ids[school_name]
        conn.execute(
            "INSERT INTO employment_quality (school_id, year, employment_rate, avg_salary, summary) VALUES (?,?,?,?,?)",
            (sid, 2024, rate, salary, summary),
        )

    conn.commit()
    print(f"已导入 {len(schools)} 所学校的数据")


if __name__ == "__main__":
    conn = sqlite3.connect("kaoyan.db")
    conn.row_factory = sqlite3.Row
    seed(conn)
    conn.close()
```

- [ ] **Step 2: 运行种子数据导入**

```bash
python -m kaoyan_agent.seed_data
```

Expected: `已导入 10 所学校的数据`

- [ ] **Step 3: Commit**

```bash
git add kaoyan_agent/seed_data.py
git commit -m "feat: add seed data (10 schools, 3 majors)"
```

---

### Task 9: 端到端验证

**Files:**
- Modify: `kaoyan_agent/cli.py` (添加 `--seed` 参数)

- [ ] **Step 1: 更新 CLI 支持 --seed 参数**

在 `cli.py` 的 `main()` 函数开头（`create_tables` 之后）添加种子数据自动导入逻辑：

```python
import sys

def main():
    # ... 前面代码不变 ...
    conn.row_factory = sqlite3.Row
    create_tables(conn)

    # 检查是否需要导入种子数据
    cursor = conn.execute("SELECT COUNT(*) FROM schools")
    if cursor.fetchone()[0] == 0:
        print("数据库为空，正在导入种子数据...")
        from kaoyan_agent.seed_data import seed
        seed(conn)
    # ... 后面代码不变 ...
```

- [ ] **Step 2: 设置 API Key 并运行**

```bash
export ANTHROPIC_API_KEY="your-key-here"
python -m kaoyan_agent.cli
```

手动测试以下场景：
1. 输入 "浙江大学计算机怎么样"（信息咨询模式）
2. 输入 "帮我推荐学校"（择校决策模式）
3. 确认 Agent 在择校模式下会追问地理位置偏好

- [ ] **Step 3: Commit**

```bash
git add kaoyan_agent/cli.py
git commit -m "feat: auto-import seed data on first run"
```

---

### Task 10: 最终检查

- [ ] **Step 1: 运行全部测试**

```bash
pytest tests/ -v
```

Expected: 全部通过

- [ ] **Step 2: 确认 .gitignore 生效**

```bash
git status
```

Expected: 不包含 `kaoyan.db`、`__pycache__`、`.superpowers/`

- [ ] **Step 3: 最终 commit**

```bash
git add -A
git commit -m "chore: final cleanup and verification"
```
