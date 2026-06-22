# Data Flow: Conversational Needs Analysis to Decision Recommendation

**Last Updated:** 2026-05-30

## High-Level Flow

```
User Chat        NeedsAnalysis        Preference        Decision Service      Orchestrator
Conversation     Agent                Weights            (Python Scoring)      (LLM Text)
                                                                                
┌───────────┐   ┌──────────────┐   ┌──────────────┐   ┌────────────────┐   ┌──────────────┐
│ NeedsChat │──>│ DeepSeek     │──>│ JSON weights  │──>│ cache check    │   │              │
│ (frontend)│   │ chat         │   │ saved to      │   │ school match   │   │ qualitative  │
│           │<──│ finalize     │   │ UserProfile   │   │ score lines    │   │ analysis     │
│           │   │              │   │               │   │ trend compute  │   │ (pros/cons   │
│           │   │              │   │               │   │ two-way weight │   │  text only)  │
│           │   │              │   │               │   │ scoring (60:40)│   │              │
│           │   │              │   │               │   │ cache write    │   │              │
└───────────┘   └──────────────┘   └──────────────┘   └────────────────┘   └──────────────┘
                                                             │                       │
                                                             └───────────────────────┘
                                                                       │
                                                                  ┌────▼────┐
                                                                  │ Frontend│
                                                                  │ Results │
                                                                  └─────────┘
```

## Step-by-Step Data Flow

### PHASE 1: Chat-based Preference Extraction

**Trigger:** User types message in NeedsChat component.

**1a: Send Chat Message**
```
Frontend: POST /api/needs-analysis/chat
Body:     { profile_id, message, history: [{role, content}] }

Backend -> NeedsAnalysisAgent.chat(history, message)
  -> OpenAI client.chat.completions.create()
  -> DeepSeek processes SYSTEM_PROMPT + history + user message
  -> Returns chat reply text + optional ```weights JSON block

If weights JSON found in response:
  -> Parse weights from ```weights ... ``` block
  -> Auto-save to UserProfile.preference_weights (JSON field)
  -> Clear RecommendationCache for this profile
  -> Returns { reply, weights, is_complete: true }
Else:
  -> Returns { reply, weights: null, is_complete: false }
```

**1b: Finalize (Force Extraction)**
```
Frontend: POST /api/needs-analysis/finalize
Body:     { profile_id, history }

Backend -> NeedsAnalysisAgent.finalize(history)
  -> DeepSeek with extraction-only prompt
  -> Always attempts to return normalized weights JSON
  -> Auto-saves to UserProfile.preference_weights
  -> Clears RecommendationCache for this profile
```

**Weights Schema** (normalized by `NeedsAnalysisAgent._normalize_weights()`):
```json
{
  "province_priority": 0.8,       // 0.0-1.0, default 0.5
  "level_priority": 0.7,          // 0.0-1.0, default 0.5
  "major_priority": 0.6,          // 0.0-1.0, default 0.5
  "score_priority": 0.5,          // 0.0-1.0, default 0.5
  "risk_tolerance": "适中",        // 保守/适中/激进
  "career_goal": "工业界",         // 学术界/工业界/公务员/创业/未定
  "preferred_cities": ["上海"],
  "preferred_majors": ["计算机"],
  "excluded_provinces": [],
  "reasoning": "学生偏好上海地区，重视学校层次，计算机方向，风险适中"
}
```

### PHASE 2: Recommendation Request

**Trigger:** User clicks "开始智能推荐" or auto-fires on DecisionPage mount.

```
Frontend: POST /api/decisions/recommend
Body:     { profile_id, target_province?, target_level?, major_keyword? }

Backend -> decision_service.recommend(db, profile_id, province, level, keyword)
```

**Step 2a: Cache Check**
```
Compute params_hash = SHA256(profile_id|province|level|keyword|preference_weights_hash)
Query RecommendationCache WHERE profile_id AND params_hash AND created_at >= today - 7 days
If found: return cached DecisionResult immediately (no LLM call)
```

**Step 2b: School Matching (SQL)**
```
If major_keyword provided:
  -> Query Matching majors by name/first_level/category LIKE keyword (limit 500)
  -> Include schools that have matching majors AND match province/level filters
  -> Extend school pool with extra schools from major match (if not already included)
Else:
  -> Query School by province, level filters (limit 15)
  -> Fallback cascade: province only -> level only -> top 10 by ranking

Cap total school pool at 30
```

**Step 2c: Score Line + Trend Batch Fetch**
```
Fetch ALL ScoreLine records for school_ids (ORDER BY year DESC)
Compute trends via _build_trends_bulk():
  -> Group score lines by (school_id, major_code)
  -> For each group, compute trend text in pure Python (no LLM):
     - Direction: 上升/下降/稳定
     - Volatility: 波动较大/小幅波动/非常稳定
     - Recent 3-year average comparison
     - Predicted next year score
  -> Compute admit ratio from applicant_count/admit_count
```

**Step 2d: Hybrid Scoring Pipeline** (`_compute_recommendations()`)

The Two-Way Weighted Scoring algorithm:

```
SCHOOL MATCH (weight: 60% when major keyword absent, adjusts with major):
  province_match = 15 (if matches target_province) else 0
  level_match    = 15 (if matches target_level) else 0
  score_match    = 10 + bonus (bonus = (estimated - recent_avg) / 2, capped ±20)
  base_score     = 40 (baseline)

  dimension_score = (province_match * w_province + level_match * w_level + score_match * w_score)
                    / (w_province + w_level + w_score)
  school_match    = base_score + dimension_score * 2   [clamped 10-100]

MAJOR MATCH (weight: 40% when keyword present):
  exact match              = 100
  substring match          = 85
  first_level match        = 70
  category match           = 55
  partial overlap (2+ char)= 30
  unknown major            = 5
  no keyword               = 50 (neutral)

FINAL SCORE = school_match * (1 - major_weight) + major_score * major_weight
  where major_weight = 0.35 + w_major * 0.3  [range 0.35-0.65]

RISK LEVEL:
  margin = 10 (激进) / 15 (适中) / 20 (保守)
  diff > margin  -> 保底
  diff < -margin -> 冲刺
  else           -> 稳妥

COMPETITION LEVEL:
  admit_ratio < 0.1  -> 竞争激烈
  0.1-0.2            -> 竞争较激烈
  >= 0.2             -> 竞争中等

Sort by match_score DESC, return top 6.
```

Dynamic preference weights from UserProfile.preference_weights are integrated:
- `w_province` from `province_priority` (default 0.5)
- `w_level` from `level_priority` (default 0.5)
- `w_major` from `major_priority` (default 0.5)
- `w_score` from `score_priority` (default 0.5)
- `risk_tolerance` adjusts safety margin thresholds

**Step 2e: Minimal LLM Call** (`_generate_qualitative_analysis()`)

Only for qualitative text generation:
```
Compact prompt with precomputed results summary (index-based)
DeepSeek response format:
{
  "items": [{"index": 1, "pros": [...], "cons": [...]}, ...],
  "analysis": "整体分析(150字内)",
  "plan_suggestion": "备考建议(100字内)"
}
```

**Step 2f: Cache + Return**
```
Combine: Python scores + LLM pros/cons text -> Final DecisionResult
Write to RecommendationCache with params_hash
Return to frontend
```

### PHASE 3: Single School+Major Analysis

**Trigger:** "AI 分析" button on a major in SchoolSearch.

```
Frontend: POST /api/decisions/analyze
Body:     { school_id, major_code, estimated_score? }

Backend -> decision_service.analyze_school_major(db, school_id, major_code, score)
  -> Fetch School, Major, ScoreLine records
  -> Python pre-computation:
     - risk_level from score diff (margin 15)
     - match_score = 50 + diff/2 [clamped 0-100]
     - competition from admit_ratio
     - trend_text from _analyze_trend_py()
  -> Minimal LLM call: compact JSON prompt, returns pros/cons/analysis/tips
  -> Return combined result
```

### PHASE 4: Study Plan Generation (from Recommendation)

**Trigger:** User clicks "为这个目标生成备考计划" from DecisionPage card.

**URL flow:**
```
DecisionPage -> /plans?school=清华大学&major=计算机&code=085404&subjects=["408"]&...

StudyPlan page reads URL params:
  -> Sets targetSchoolName, targetMajorCode, examSubjectsForPlan from URL
  -> User fills/edits profile form
  -> POST /api/study-plans/generate { profile_id, target_school_id, target_major_code, exam_subjects }
  -> StudyPlanAgent.generate_plan(profile, school, major, subjects)
     -> DeepSeek with SYSTEM_PROMPT (three-phase plan generation)
     -> Returns phases[], daily_schedule, materials, tips
  -> Saved to StudyPlan table with deduplication check
  (If existing draft/active plan for same profile+school+major, returns cached)
```

### Related Areas

- [backend.md](backend.md) -- Backend agents, services, API routes
- [frontend.md](frontend.md) -- Frontend pages and components
- [database.md](database.md) -- Database models and schema
- [integrations.md](integrations.md) -- DeepSeek, ChromaDB, crawler service details

### Architecture Notes

1. **Hybrid pipeline**: Heavy computation in Python (fast, cheap, reproducible), LLM only for natural language text generation (slow, expensive, creative). This minimizes API costs and response times.

2. **Two-way weighted scoring**: Separates school match from major match, allowing the system to recommend schools outside the preferred province if they have exceptionally strong major matches (and vice versa).

3. **Preference weight integration**: Every step of the scoring pipeline reads from `UserProfile.preference_weights`, which was extracted conversationally by the NeedsAnalysisAgent. This creates a direct feedback loop from the chat to the recommendation math.

4. **Cache strategy**: `RecommendationCache` prevents redundant LLM calls for identical parameter sets within 7 days. The cache is invalidated whenever preference weights change (via needs-analysis or manual save).

5. **Risk tolerance adjustment**: The `risk_tolerance` dimension (conservative/moderate/aggressive) shifts the safety margin thresholds (20/15/10 points respectively), directly controlling how aggressively the system recommends "reach" vs "safety" schools.
