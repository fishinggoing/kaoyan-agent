# Frontend Codemap

**Last Updated:** 2026-05-30
**Technology:** React 19, TypeScript 6.0, Vite 8, Tailwind CSS 4, React Router 7

## Entry Points

| File | Purpose |
|------|---------|
| `frontend/src/main.tsx` | React DOM render, BrowserRouter wrapper |
| `frontend/src/App.tsx` | Shell layout: sticky header with nav, Routes definition, footer |
| `frontend/vite.config.ts` | Vite config: React plugin, Tailwind, dev proxy /api -> localhost:8000 |

## File Tree

```
frontend/
  index.html                      # SPA entry
  vite.config.ts                  # Build config
  package.json                    # Dependencies
  tsconfig.json                   # Base TS config
  tsconfig.app.json               # App TS config
  tsconfig.node.json              # Node TS config
  eslint.config.js                # ESLint flat config
  playwright.config.ts            # Playwright E2E config
  public/
    favicon.svg
    icons.svg
  src/
    main.tsx                      # Root mount + BrowserRouter
    App.tsx                       # Layout + routing + nav
    App.css                       # App-level styles
    index.css                     # Tailwind imports + global styles
    api/
      client.ts                   # HTTP client with all API methods
    types/
      index.ts                    # All TypeScript interfaces
    pages/
      HomePage.tsx                # Landing / feature showcase
      SchoolSearch.tsx            # Guided province->level->school->major browser
      ScoreAnalysis.tsx           # Score line query, chart, trend analysis
      NeedsChat.tsx               # Conversational needs analysis chat UI
      DecisionPage.tsx            # AI recommendation display
      StudyPlan.tsx               # Profile creation + plan generation + display
    components/
      SchoolCard.tsx              # School info card
      ScoreChart.tsx              # Recharts score line chart
      SearchableSelect.tsx        # Generic searchable dropdown
    assets/
      hero.png
      react.svg
      vite.svg
  e2e/
    home.spec.ts                  # Home page E2E test
    schools.spec.ts               # School search E2E test
    decisions.spec.ts             # Decision page E2E test
```

## Routing (React Router v7)

| Path | Component | Description |
|------|-----------|-------------|
| `/` | `HomePage` | Landing page with feature cards and usage guide |
| `/schools` | `SchoolSearch` | Guided 4-step school/major browser |
| `/scores` | `ScoreAnalysis` | Score line query with chart + saved comparison cards |
| `/needs` | `NeedsChat` | Conversational AI needs assessment chat |
| `/decisions` | `DecisionPage` | AI recommendation results with expandable cards |
| `/plans` | `StudyPlan` | Profile form + AI-generated study plan display |

Navigation bar in `App.tsx` highlights active route and shows all 6 nav items with Lucide icons.

## Pages

### HomePage
- Marketing landing with feature cards (院校查询, 分数线分析, 备考规划)
- "How to use" section with 3 numbered steps
- Hero image placeholder

### SchoolSearch
- **4-step guided wizard:** province -> level -> school -> major
- Step 1: Province grid with school counts from `/api/schools/filters`
- Step 2: Level selection (filtered by available counts)
- Step 3: School list using `SchoolCard` component
- Step 4: Major list with per-major AI analysis button (POST `/api/decisions/analyze`)
- Breadcrumb navigation for step backtracking
- AI analysis results show risk level badge, match score, pros/cons, tips

### ScoreAnalysis
- Searchable school selector (`SearchableSelect`) + major selector
- Score line trend chart via `ScoreChart` (Recharts LineChart)
- Trend analysis text (from Python computation)
- Data table with year-by-year score breakdown
- "Save to comparison" button -> `ScoreCard` CRUD
- Saved comparison cards grid with mini-trend indicators

### NeedsChat
- Left sidebar: conversation history (localStorage persisted)
- Chat area: messages display, text input, send/finalize buttons
- Profile selector dropdown (loads from `/api/profiles/{id}`)
- Multiple concurrent conversations per profile
- "Finalize" button forces weight extraction via POST `/api/needs-analysis/finalize`
- Auto-saves weights to user profile on extraction
- Empty state: bot greeting with instructions

### DecisionPage
- Profile selector + config panel (target province, level, major keyword)
- Loading states: "computing" -> "analyzing" phases with animated icons
- Results: analysis overview card + expandable recommendation cards
- Each recommendation card: risk level badge, match score bar, trend/competition, pros/cons, exam subjects
- "Generate study plan" link passes params via URL query to `/plans`
- Auto-fires recommendation on mount (cache hit if params unchanged)

### StudyPlan
- Profile creation/editing form (nickname, school, major, exam config, subject strengths)
- Target school search + major code input
- AI plan generation with deduplication (force regenerate option)
- Plan list sidebar + detail view
- Phases timeline: 基础/强化/冲刺 with expandable accordion
- Daily schedule: weekday/weekend time tables
- Materials recommendations
- Tips section
- Plan status management (draft -> active)

## Shared Components

### SchoolCard
- Displays school name, province/city, level badge (color-coded), type, ranking
- Conditional: description excerpt, website link, graduate school indicator

### ScoreChart
- Recharts `LineChart` with total score as primary line
- Optional dashed lines for politics, english, business1, business2
- Responsive container, auto-scaled Y-axis
- Tooltip with styled content

### SearchableSelect<T>
- Generic searchable dropdown with debounced input (250ms)
- Keyboard navigation (arrows, enter, escape)
- Click-outside-to-close
- Loading state with spinner
- Selected state shows label with clear button
- Highlighted index tracking

## API Client (`src/api/client.ts`)

Central `api` object with namespaced methods:

```
api.health()
api.schools.filters()
api.schools.options(params)
api.schools.list(params)
api.schools.search(query, page, size)
api.schools.get(id)
api.majors.list(params)
api.majors.get(id)
api.scoreLines.list(params)
api.scoreLines.trend(schoolId, majorCode, years)
api.decisions.recommend(body)
api.decisions.analyze(schoolId, majorCode, estimatedScore)
api.profiles.create(data)
api.profiles.get(id)
api.profiles.update(id, data)
api.studyPlans.list(params)
api.studyPlans.get(id)
api.studyPlans.create(data)
api.studyPlans.generate(data)
api.studyPlans.update(id, data)
api.studyPlans.delete(id)
api.studyPlans.adjust(id, data)
api.scoreCards.list(params)
api.scoreCards.create(data)
api.scoreCards.delete(id)
api.needsAnalysis.chat(data)
api.needsAnalysis.finalize(data)
api.needsAnalysis.getWeights(profileId)
api.needsAnalysis.saveWeights(profileId, weights)
```

All methods return `Promise<ApiResponse<T>>` where `ApiResponse = {success, data, error}`.

## Key Data Flow Patterns

1. **Conversational Preferences:** NeedsChat -> POST `/api/needs-analysis/chat` -> DeepSeek -> weights JSON -> saved to UserProfile.preference_weights
2. **Recommendations:** DecisionPage -> POST `/api/decisions/recommend` -> decision_service (Python scoring) + orchestrator (LLM) -> cached results
3. **Study Plans:** URL params from DecisionPage -> `/plans` -> profile form -> POST `/api/study-plans/generate` -> DeepSeek -> saved plan

## Dependencies (package.json)

| Package | Purpose |
|---------|---------|
| `react` / `react-dom` | UI framework |
| `react-router-dom` | Client-side routing |
| `tailwindcss` / `@tailwindcss/vite` | Utility CSS |
| `lucide-react` | Icon library |
| `recharts` | Score line charts |
| `@playwright/test` | E2E testing |
| `typescript` | Type checking |
| `vite` / `@vitejs/plugin-react` | Build + dev server |
| `eslint` | Linting |

## E2E Tests

```
frontend/e2e/
  home.spec.ts      # Home page loads and displays features
  schools.spec.ts   # School search flow
  decisions.spec.ts # Decision page flows
```

Uses Playwright with `@playwright/test` v1.60+.
