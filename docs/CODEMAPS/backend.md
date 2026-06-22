# Backend Codemap

**Last Updated:** 2026-05-30
**Technology:** Python 3.11+, FastAPI, SQLAlchemy 2.0, SQLite, ChromaDB, DeepSeek (OpenAI-compatible)

## Entry Points

| File | Purpose |
|------|---------|
| `backend/app/main.py` | FastAPI app creation, CORS, lifespan (DB init, scheduler), static file serving |
| `backend/app/config.py` | Pydantic Settings from `.env` file |
| `backend/app/agents/orchestrator.py` | Central multi-agent coordinator for recommendations |

## File Tree (source only)

```
backend/app/
  __init__.py
  main.py                         # FastAPI app
  config.py                       # Env-based settings
  api/
    __init__.py                   # Router aggregator
    schools.py                    # CRUD + search endpoints
    majors.py                     # Filter/list majors
    score_lines.py                # Score line query + trend
    score_cards.py                # Saved comparison cards CRUD
    study_plans.py                # Study plan CRUD + AI generation
    decisions.py                  # AI recommendation + school analysis
    profiles.py                   # User profile CRUD
    needs_analysis.py             # Conversational needs assessment chat
  agents/
    needs_analysis.py             # Conversational preference extraction agent
    orchestrator.py               # Recommendation orchestration agent
    study_plan_agent.py           # Study plan generation agent
    info_collector.py             # Web crawling + info extraction agent
    score_analyzer.py             # Score line trend analysis agent
  services/
    school_service.py             # School CRUD + multi-field search + filters
    score_service.py              # Score line query + trend analysis (Python)
    decision_service.py           # Hybrid recommendation engine (Python + LLM)
    study_plan_service.py         # UserProfile + StudyPlan CRUD
    crawl_service.py              # APScheduler periodic web crawler (研招网)
  models/
    __init__.py                   # All ORM models: School, Major, ScoreLine, UserProfile, StudyPlan, RecommendationCache, ScoreCard
  db/
    database.py                   # SQLAlchemy engine + session factory
    vector_store.py               # ChromaDB client + school/major vector indexing
  data/
    province_mapping.py           # GB/T 2260 province codes + name-to-province mapping
    school_levels.py              # C9/985/211/双一流 school code sets
  utils/
    exceptions.py                 # AppException, NotFoundError, ValidationError, AgentError
    logging.py                    # Logging setup
```

## API Routes

All routes are mounted under `/api`. All responses follow `{success: bool, data: T | null, error: string | null}`.

### Health

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health check (DB, scheduler status) |

### Schools

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/schools/` | List schools with filters (name, province, level, school_type, page, size) |
| GET | `/api/schools/filters` | Available filter options (provinces with counts, levels with counts) |
| GET | `/api/schools/options` | Lightweight school list for cascade selectors |
| GET | `/api/schools/search` | Multi-field relevance search (name, description, province, city) |
| GET | `/api/schools/{school_id}` | Get school detail |
| POST | `/api/schools/` | Create school |
| PUT | `/api/schools/{school_id}` | Update school |
| DELETE | `/api/schools/{school_id}` | Delete school |

### Majors

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/majors/` | List majors with filters (name, code, category, school_id) |
| GET | `/api/majors/categories` | List distinct major categories |
| GET | `/api/majors/{major_id}` | Get major detail |

### Score Lines

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/score-lines/` | List score lines with filters (school_id, major_code, year) |
| GET | `/api/score-lines/trend` | Score trend for school+major over N years |

### Score Cards

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/score-cards/` | List saved comparison cards |
| POST | `/api/score-cards/` | Save a score comparison card |
| DELETE | `/api/score-cards/{card_id}` | Delete a card |

### User Profiles

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/profiles/` | Create user profile |
| GET | `/api/profiles/{profile_id}` | Get user profile |
| PUT | `/api/profiles/{profile_id}` | Update user profile |

### Study Plans

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/study-plans/` | List plans (profile_id, status filter) |
| POST | `/api/study-plans/` | Create plan manually |
| POST | `/api/study-plans/generate` | AI-generate study plan (deduplication logic) |
| GET | `/api/study-plans/{plan_id}` | Get plan with expanded phases/daily schedule |
| PUT | `/api/study-plans/{plan_id}` | Update plan |
| DELETE | `/api/study-plans/{plan_id}` | Delete plan |
| POST | `/api/study-plans/{plan_id}/adjust` | AI-adjust plan based on progress |

### Decisions

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/decisions/recommend` | AI recommendation for schools (pre-computation + LLM) |
| POST | `/api/decisions/analyze` | AI analysis for a single school+major combo |

### Needs Analysis

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/needs-analysis/chat` | Send message in the needs analysis conversation |
| POST | `/api/needs-analysis/finalize` | Force extract preference weights from conversation |
| GET | `/api/needs-analysis/weights/{profile_id}` | Get saved preference weights |
| POST | `/api/needs-analysis/weights/{profile_id}` | Manually save/update preference weights |

## Multi-Agent System

All agents use DeepSeek via the OpenAI-compatible API (`openai` Python package).

### 1. NeedsAnalysisAgent (`app/agents/needs_analysis.py`)

**Singleton:** `needs_analysis_agent`

- **Purpose:** Conversational needs assessment via DeepSeek
- **System prompt:** Acts as a professional grad school advisor, asks targeted questions about career goals, geography preferences, school tier trade-offs, risk tolerance, subject strengths
- **Weights extraction:** Appends ```weights {JSON}``` block to response when sufficient info gathered
- **Key methods:**
  - `chat(history, message)` -- Process a user message, return reply + optional weights
  - `finalize(history)` -- Force weight extraction from full conversation history
- **Schema output:** `province_priority`, `level_priority`, `major_priority`, `score_priority` (0-1), `risk_tolerance`, `career_goal`, `preferred_cities`, `preferred_majors`, `excluded_provinces`, `reasoning`
- **Temperature:** 0.5 (chat), 0.3 (finalize)
- **Max tokens:** 800 (chat), 500 (finalize)

### 2. OrchestratorAgent (`app/agents/orchestrator.py`)

**Singleton:** `orchestrator`

- **Purpose:** Generates school recommendations via DeepSeek
- **System prompt:** Expert counselor analyzing student profile + matching schools + score data + trends
- **Output:** JSON with `recommendations[]` (school_name, risk_level, match_score, score_trend, competition, pros, cons) + `analysis` + `plan_suggestion`
- **Temperature:** 0.4
- **Max tokens:** 3000
- **Key methods:**
  - `recommend(profile, schools, score_data, trends, exam_subjects_lookup)` -- Full recommendation
  - `analyze_single(school, major, score_lines, estimated_score)` -- Single school+major analysis

### 3. StudyPlanAgent (`app/agents/study_plan_agent.py`)

**Singleton:** `study_plan_agent`

- **Purpose:** Generates personalized study plans in three phases (基础/强化/冲刺)
- **Key methods:**
  - `generate_plan(profile, school_name, major_name, exam_subjects)` -- Create plan
  - `adjust_plan(current_plan, completed_tasks, progress_notes)` -- Adjust based on progress
- **Output:** `phases[]`, `daily_schedule` (weekday/weekend), `materials`, `tips`, `total_weeks`

### 4. InfoCollectorAgent (`app/agents/info_collector.py`)

**Singleton:** `info_collector`

- **Purpose:** Web crawler + DeepSeek for extracting structured school/major info
- **Method:**
  1. Crawl 研招网 (yz.chsi.com.cn) pages via httpx + BeautifulSoup
  2. Pass raw HTML to DeepSeek for structured JSON extraction
- **Output:** `CollectResult(schools[], majors[], summary)`

### 5. ScoreAnalyzerAgent (`app/agents/score_analyzer.py`)

**Singleton:** `score_analyzer`

- **Purpose:** DeepSeek-powered score trend analysis
- **Output:** `trend_direction`, `volatility`, `competition_level`, `predictions`, `key_findings`, `recommendation`
- **Methods:** `analyze(school, major, score_data)`, `compare_schools(comparisons)`

## Services Layer

### School Service (`app/services/school_service.py`)
- `get_filter_options()` -- Province + level counts for guided UI
- `get_school_options()` -- Lightweight cascade selector data (excludes sub-units)
- `list_schools()` -- Filtered paginated list
- `search_schools()` -- Multi-field relevance search with CASE-based weighting
- CRUD: `get_school`, `create_school`, `update_school`, `delete_school`

### Score Service (`app/services/score_service.py`)
- `list_score_lines()` -- Filtered paginated score lines
- `get_trend()` -- Trend analysis for school+major (pure Python, no LLM)
- `_analyze_trend()` -- Computes direction, volatility, predictions purely from data

### Decision Service (`app/services/decision_service.py`)

This is the central recommendation engine implementing the **hybrid scoring pipeline**:

1. **Cache check**: Look up `RecommendationCache` by `params_hash` (7-day TTL)
2. **School matching**: SQL queries (province + level filters, fallback cascading)
3. **Major keyword expansion**: Bidirectional join -- find schools with matching majors
4. **Score line batch fetch**: All score lines for matched schools
5. **Python trend computation**: `_build_trends_bulk()` -- pure Python, no LLM
6. **Two-way weighted scoring**: `_compute_recommendations()`
   - School match (60% weight): province_match + level_match + score_match
   - Major match (40% weight): keyword similarity scoring
   - Dynamic preference weights from `profile.preference_weights`
   - Risk tolerance-adjusted safety margins
7. **Qualitative LLM call**: `_generate_qualitative_analysis()` -- minimal DeepSeek call for pros/cons/analysis by index
8. **Cache write**: Save results for 7-day reuse

### Study Plan Service (`app/services/study_plan_service.py`)
- CRUD for `UserProfile` and `StudyPlan` models

### Crawl Service (`app/services/crawl_service.py`)
- APScheduler-based periodic crawler (weekly Sunday 3am)
- Targets 研招网 (yz.chsi.com.cn) for school majors
- Uses httpx + BeautifulSoup for HTML parsing
- `start_scheduler()` / `stop_scheduler()` called from lifespan

## Utilities

| File | Purpose |
|------|---------|
| `app/utils/exceptions.py` | `AppException`, `NotFoundError`(404), `ValidationError`(422), `AgentError`(500) |
| `app/utils/logging.py` | Structured logging to stdout, suppresses httpx/chromadb noise |

## Data Files

| File | Purpose |
|------|---------|
| `app/data/province_mapping.py` | GB/T 2260 province codes, `SCHOOL_TO_PROVINCE` lookup, `NAME_PROVINCE_HINTS` keyword matching |
| `app/data/school_levels.py` | Hardcoded sets of C9/985/211/双一流 school codes with names |

## Tests

```
backend/tests/
  conftest.py          # Pytest fixtures (test client, test DB)
  test_agents.py       # Agent response parsing tests
  test_api_majors.py   # Major API endpoint tests
  test_api_profiles.py # Profile API endpoint tests
  test_api_schools.py  # School API endpoint tests
  test_api_scores.py   # Score line API tests
  test_exceptions.py   # Custom exception tests
  test_models.py       # ORM model validation tests
  test_services.py     # Service layer tests
```
