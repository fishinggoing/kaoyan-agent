# External Integrations Codemap

**Last Updated:** 2026-05-30

## 1. DeepSeek API (LLM)

**Purpose:** Powers all 5 AI agents for natural language understanding, generation, and analysis.

**Configuration** (in `.env` or env vars):
```
DEEPSEEK_API_KEY=sk-...
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat
```

**Type:** OpenAI-compatible API. All agents use the `openai` Python package with custom `base_url` and `api_key`.

**Usage Table:**

| Consumer | Model | Temperature | Max Tokens | Purpose |
|----------|-------|-------------|-------------|---------|
| `NeedsAnalysisAgent.chat()` | deepseek-chat | 0.5 | 800 | Conversational preference extraction |
| `NeedsAnalysisAgent.finalize()` | deepseek-chat | 0.3 | 500 | Force weight extraction from history |
| `OrchestratorAgent.recommend()` | deepseek-chat | 0.4 | 3000 | Full recommendation generation |
| `OrchestratorAgent.analyze_single()` | deepseek-chat | 0.4 | 2000 | Single school+major analysis |
| `OrchestratorAgent._generate_qualitative_analysis()` | deepseek-chat | 0.4 | 600 | Minimal LLM for pros/cons text |
| `StudyPlanAgent.generate_plan()` | deepseek-chat | 0.5 | 3000 | Study plan generation |
| `StudyPlanAgent.adjust_plan()` | deepseek-chat | 0.4 | 3000 | Plan adjustment |
| `InfoCollectorAgent._extract_structured()` | deepseek-chat | 0.3 | 2000 | HTML to structured data extraction |
| `ScoreAnalyzerAgent.analyze()` | deepseek-chat | 0.3 | 1500 | Score trend analysis |
| `ScoreAnalyzerAgent.compare_schools()` | deepseek-chat | 0.3 | 1500 | School comparison |

**Error handling:** All agents wrap API calls in try/except and return graceful fallback responses with error logging.

**Dependency:** `openai` Python package (^1.57.0)

## 2. ChromaDB (Vector Store)

**Purpose:** Semantic vector search for schools and majors.

**Configuration:**
```
CHROMA_PERSIST_DIR=./chroma_data
```

**Collections:**

| Collection | Content | Embedding |
|------------|---------|-----------|
| `schools` | School name + province + city + description | DefaultEmbeddingFunction (all-MiniLM-L6-v2, ~79MB) |
| `majors` | Major name + category + first_level | DefaultEmbeddingFunction (same model) |

**Key Functions** (in `app/db/vector_store.py`):

| Function | Description |
|----------|-------------|
| `get_chroma_client()` | Returns singleton PersistentClient |
| `get_school_collection()` | Get/create schools collection |
| `get_major_collection()` | Get/create majors collection |
| `index_schools(schools)` | Batch upsert school documents |
| `search_schools_vector(query, top_k)` | Semantic search returning school_id + relevance score |

**Embedding Model:** ONNX-based `all-MiniLM-L6-v2` from HuggingFace. Downloads automatically on first use. Falls back gracefully (returns empty results) if download fails or model unavailable.

**Resilience:** All vector store operations are wrapped in try/except. When embeddings are unavailable, the system falls back to SQL-based multi-field relevance search (already implemented in `school_service.search_schools()`).

**Dependency:** `chromadb` Python package (^0.5.0)

## 3. APScheduler (Task Scheduler)

**Purpose:** Periodic web crawling for school data updates.

**Configuration:** Runs in the FastAPI lifespan (`app/main.py`).

**Jobs:**

| Job ID | Schedule | Function | Description |
|--------|----------|----------|-------------|
| `crawl_school_data` | Weekly Sunday 3:00 AM | `crawl_job()` | Crawl 研招网 for school majors |
| `crawl_heartbeat` | Every 6 hours | logger.info | Health check log |

**Lifecycle:**
- `start_scheduler()` called during FastAPI `lifespan` startup
- `stop_scheduler()` called during FastAPI `lifespan` shutdown
- Manual trigger available via `trigger_crawl_now(school_ids)`

**Dependency:** `apscheduler` Python package (^3.10.0)

## 4. 研招网 (Chinese Graduate Admission Website)

**Purpose:** Public data source for school major listings.

**Crawl Targets:**
```
https://yz.chsi.com.cn/zsml/queryAction.do   # Major search
https://yz.chsi.com.cn/sch/search.do          # School search
```

**Crawler Details** (in `app/services/crawl_service.py`):
- Uses `httpx.AsyncClient` with polite delays (3s between requests)
- Parses HTML with `BeautifulSoup` (lxml parser)
- Targets top-ranked schools first (batch of 20)
- Upserts new majors to database; skips existing (by code + school_id)
- Province code mapping for query parameters

**Dependencies:** `httpx`, `beautifulsoup4`, `lxml`

## 5. Environment Variables (`.env`)

```
DEEPSEEK_API_KEY=                          # Required for all AI agent features
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat
DATABASE_URL=sqlite:///./gradschool.db     # SQLite file path
CHROMA_PERSIST_DIR=./chroma_data           # ChromaDB persistence
HOST=0.0.0.0                               # Backend bind host
PORT=8000                                  # Backend bind port
DEBUG=false                                # Debug mode
ALLOW_ORIGINS=http://localhost:5173        # CORS origins (comma-separated)
STATIC_DIR=                                # Production frontend static dir
```

## 6. Frontend Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| react / react-dom | ^19.2.6 | UI framework |
| react-router-dom | ^7.15.1 | Client-side routing |
| tailwindcss | ^4.3.0 | Utility-first CSS |
| lucide-react | ^1.16.0 | Icon set |
| recharts | ^3.8.1 | Score line charts |
| @playwright/test | ^1.60.0 | E2E testing |
| vite | ^8.0.12 | Build tool |
| typescript | ~6.0.2 | Type checking |

## 7. Python Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| fastapi | ^0.115.0 | Web framework |
| uvicorn | ^0.32.0 | ASGI server |
| sqlalchemy | ^2.0.36 | ORM |
| alembic | ^1.14.0 | Migrations |
| pydantic | ^2.10.0 | Validation |
| pydantic-settings | ^2.6.0 | Settings management |
| openai | ^1.57.0 | DeepSeek API client |
| chromadb | ^0.5.0 | Vector store |
| httpx | ^0.28.0 | HTTP client (crawler) |
| beautifulsoup4 | ^4.12.0 | HTML parsing |
| lxml | ^5.3.0 | XML parser |
| apscheduler | ^3.10.0 | Task scheduling |
| python-dotenv | ^1.0.0 | Env file loading |
| aiofiles | ^24.0.0 | Async file I/O |
| pytest | ^8.3.0 | Testing |
| pytest-asyncio | ^0.24.0 | Async test support |
| pytest-cov | ^6.0.0 | Coverage reporting |
