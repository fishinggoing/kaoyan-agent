# GradSchool Advisor -- Codemap Index

**Last Updated:** 2026-05-30
**Project:** GradSchool Advisor (kaoyan) -- GradSchool Advisor for Chinese Graduate Entrance Exam
**Tech Stack:** Python FastAPI + SQLAlchemy + SQLite + ChromaDB + DeepSeek API / React 18 + Vite + TypeScript + Tailwind CSS

## Project Structure

```
e:\try-agent/
  backend/              # Python FastAPI backend
    app/                # Application package
      api/              # REST API routers
      agents/           # Multi-agent system (DeepSeek LLM agents)
      services/         # Business logic layer
      models/           # SQLAlchemy ORM models
      db/               # Database engine + ChromaDB vector store
      data/             # Static data (province mappings, school levels)
      utils/            # Exceptions, logging
    migrations/         # Alembic migration config
    scripts/            # Data seeding scripts
    tests/              # Pytest test suite
  frontend/             # React SPA
    src/
      api/              # HTTP client
      pages/            # Route-level pages
      components/       # Shared UI components
      types/            # TypeScript type definitions
    e2e/                # Playwright E2E tests
```

## Codemap Areas

| Map | Description | Key Files |
|-----|-------------|-----------|
| [backend.md](backend.md) | Backend architecture: API routes, agents, services, models, database | `app/main.py`, `app/api/*.py`, `app/agents/*.py`, `app/services/*.py` |
| [frontend.md](frontend.md) | Frontend structure: pages, components, API client, types | `src/App.tsx`, `src/pages/*.tsx`, `src/components/*.tsx`, `src/api/client.ts` |
| [database.md](database.md) | Database schema: tables, columns, relationships, enums | `app/models/__init__.py`, migrations |
| [integrations.md](integrations.md) | External services: DeepSeek API, ChromaDB, APScheduler, 研招网 crawler | `app/agents/*.py`, `app/db/vector_store.py`, `app/services/crawl_service.py` |
| [data-flow.md](data-flow.md) | Data flow: conversational needs-analysis to decision recommendation | Cross-cutting: NeedsChat > needs_analysis > weights > decision_service > orchestrator |

## Architecture Overview

```
Frontend (React + Vite)          Backend (FastAPI)               External
┌─────────────────────┐         ┌──────────────────────┐       ┌──────────┐
│  BrowserRouter       │         │  app/main.py         │       │ DeepSeek  │
│  ┌─ HomePage ───────┐│ HTTP    │  ┌─ API Routers ────┐│ API   │ API      │
│  │ SchoolSearch     ││◄───────►│  │ /schools          ││◄─────►│ (OpenAI  │
│  │ ScoreAnalysis    ││         │  │ /majors           ││       │  compat) │
│  │ NeedsChat        ││         │  │ /needs-analysis   ││       └──────────┘
│  │ DecisionPage     ││         │  │ /decisions        ││       ┌──────────┐
│  │ StudyPlan        ││         │  │ /study-plans      ││       │ ChromaDB │
│  └──────────────────┘│         │  │ /profiles         ││◄─────►│ (vector  │
│                      │         │  │ /score-lines      ││       │  store)  │
│                      │         │  │ /score-cards      ││       └──────────┘
│                      │         │  ├─ Agents ─────────┤│       ┌──────────┐
│                      │         │  │ NeedsAnalysis    ││       │ 研招网   │
│                      │         │  │ Orchestrator     ││◄─────►│ (crawler)│
│                      │         │  │ StudyPlan        ││       └──────────┘
│                      │         │  │ InfoCollector    ││
│                      │         │  │ ScoreAnalyzer    ││
│                      │         │  ├─ Services ───────┤│
│                      │         │  │ decision_service ││
│                      │         │  │ school_service   ││
│                      │         │  │ score_service    ││
│                      │         │  │ study_plan_svc   ││
│                      │         │  └─ crawl_service  ─┘│
│                      │         │  ┌─ SQLAlchemy ──────┤│
│                      │         │  │ SQLite DB         ││
│                      │         │  └───────────────────┘│
└─────────────────────┘         └──────────────────────┘
```

## Entry Points

| Service | Entry File | Port/Command |
|---------|-----------|-------------|
| Backend | `backend/app/main.py` | `0.0.0.0:8000` |
| Frontend | `frontend/src/main.tsx` | `localhost:5173` (dev) |
| Dev command | `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000` | Poetry script |
| Frontend dev | `vite` | port 5173, proxy /api to 8000 |

## Key Design Patterns

1. **Multi-Agent Architecture**: 5 agents (NeedsAnalysis, Orchestrator, InfoCollector, ScoreAnalyzer, StudyPlan) coordinate via DeepSeek LLM
2. **Hybrid Scoring Pipeline**: Python pre-computation (two-way weighted scoring) + minimal LLM call for qualitative text only
3. **API Envelope Pattern**: All endpoints return `{success, data, error}` envelope
4. **Conversational Preference Extraction**: Free-text chat -> DeepSeek -> structured preference_weights JSON
5. **Caching**: RecommendationCache table (7-day TTL) keyed by params_hash
