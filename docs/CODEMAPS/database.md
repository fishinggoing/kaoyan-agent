# Database Codemap

**Last Updated:** 2026-05-30
**Technology:** SQLAlchemy 2.0 ORM, SQLite (file-based), Alembic migrations

## Connection

- **URL:** `sqlite:///./gradschool.db` (configurable via `DATABASE_URL` env)
- **Engine args:** `check_same_thread=False` for SQLite
- **Session factory:** `SessionLocal` via `sessionmaker`
- **Dependency:** `get_db()` yields `Session` for FastAPI dependency injection

## Entity Relationship Diagram

```
schools 1──────* majors
  │                 │
  │                 │
  │                 │
  *                 │
score_lines ────────┘ (by school_id + major_code)

user_profiles 1─────* study_plans
       │
       │ (preference_weights JSON)
       │
       * (via params_hash)
recommendation_cache

score_cards (standalone, no FK)
```

## Tables

### schools

Schools table -- Chinese graduate-school-hosting institutions.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | Integer | PK, autoincrement | |
| name | String(100) | NOT NULL, indexed | School name |
| province | String(50) | NOT NULL | Province (省) |
| city | String(50) | NOT NULL | City (市) |
| level | Enum(SchoolLevel) | NOT NULL | C9, 985, 211, 双一流, 省属重点, 普通 |
| school_type | Enum(SchoolType) | NOT NULL | 综合, 理工, 师范, 财经, 农林, 医药, 文法, 艺体 |
| is_graduate_school | Boolean | default=False | Has graduate school |
| website | String(200) | nullable | |
| description | Text | nullable | |
| ranking_national | Integer | nullable | National ranking |
| graduate_school_url | String(200) | nullable | |
| created_at | Date | default=today | |

**Relationships:** `majors` -> `Major`

### majors

Majors/programs offered at each school.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | Integer | PK, autoincrement | |
| code | String(10) | NOT NULL, indexed | 专业代码 (e.g. "085404") |
| name | String(100) | NOT NULL | 专业名称 |
| category | String(50) | NOT NULL | 学科门类 (工学, 理学, etc.) |
| first_level | String(100) | NOT NULL | 一级学科 |
| degree_level | Enum(DegreeLevel) | NOT NULL | 硕士 / 博士 |
| exam_subjects | Text | nullable | JSON array of exam subjects |
| description | Text | nullable | |
| employment_prospect | Text | nullable | |
| school_id | Integer | FK -> schools.id, NOT NULL | |

**Relationships:** `school` -> `School`

### score_lines

Historical score line data for each school+major by year.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | Integer | PK, autoincrement | |
| school_id | Integer | FK -> schools.id, NOT NULL, indexed | |
| major_code | String(10) | NOT NULL, indexed | 专业代码 |
| year | Integer | NOT NULL, indexed | |
| category | String(10) | NOT NULL | 学硕/专硕 |
| total_score | Integer | NOT NULL | 复试线总分 |
| politics_score | Integer | nullable | |
| english_score | Integer | nullable | |
| business_score_1 | Integer | nullable | 业务课1 |
| business_score_2 | Integer | nullable | 业务课2 |
| applicant_count | Integer | nullable | 报考人数 |
| admit_count | Integer | nullable | 录取人数 |
| is_national_line | Boolean | default=False | 是否为国家线 |

### user_profiles

Student user profiles storing all personal info and preferences.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | Integer | PK, autoincrement | |
| nickname | String(50) | NOT NULL | |
| undergraduate_school | String(100) | nullable | 本科院校 |
| undergraduate_major | String(100) | nullable | 本科专业 |
| target_province | String(50) | nullable | |
| target_level | String(50) | nullable | C9/985/211 etc. |
| estimated_score | Integer | nullable | |
| available_hours_per_day | Integer | nullable | |
| exam_year | Integer | nullable | |
| notes | Text | nullable | Free-text notes |
| exam_config | Text | nullable | JSON: `{"math":"数一","english":"英一","politics":"政治","专业课":"408"}` |
| subject_strengths | Text | nullable | JSON: `{"数学":"弱","英语":"强","政治":"中","专业课":"中"}` |
| preference_weights | Text | nullable | JSON: `{"province_priority":0.8,"level_priority":0.7,...}`  |
| created_at | Date | default=today | |

### study_plans

AI-generated or manually created study plans.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | Integer | PK, autoincrement | |
| user_profile_id | Integer | FK -> user_profiles.id, NOT NULL | |
| target_school_id | Integer | FK -> schools.id, nullable | |
| target_major_code | String(10) | nullable | |
| title | String(200) | NOT NULL | e.g. "清华大学 备考计划" |
| status | Enum(PlanStatus) | default=DRAFT | draft / active / completed / archived |
| phases_json | Text | nullable | JSON: phase array with name, weeks, focus, subjects, tasks, weekly_hours, checkpoint |
| daily_tasks_json | Text | nullable | JSON: weekday/weekend schedule |
| start_date | Date | default=today | |
| end_date | Date | nullable | |
| notes | Text | nullable | JSON: `{"materials":[],"tips":[],"total_weeks":36}` |
| created_at | Date | default=today | |

### recommendation_cache

Cached AI recommendation results keyed by input params hash.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | Integer | PK, autoincrement | |
| profile_id | Integer | NOT NULL, indexed | |
| params_hash | String(64) | NOT NULL, UNIQUE | SHA256 of (profile_id + province + level + keyword + pw_hash) |
| result_json | Text | NOT NULL | Full recommendation result |
| created_at | Date | default=today | 7-day TTL applied in service |

### score_cards

User-saved score comparison cards.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | Integer | PK, autoincrement | |
| school_name | String(100) | NOT NULL | |
| major_name | String(100) | NOT NULL | |
| major_code | String(10) | NOT NULL | |
| exam_subjects | Text | nullable | JSON array |
| score_data_json | Text | NOT NULL | JSON array of score lines |
| created_at | Date | default=today | |

## Enums

### SchoolLevel
`C9` | `985` | `211` | `双一流` | `省属重点` | `普通`

### SchoolType
`综合` | `理工` | `师范` | `财经` | `农林` | `医药` | `文法` | `艺体`

### DegreeLevel
`硕士` | `博士`

### PlanStatus
`draft` | `active` | `completed` | `archived`

## Key Indexes

- `schools.name` - B-tree index for name search
- `majors.code` - B-tree index for code lookup
- `majors.school_id` - FK index (implicit)
- `score_lines.school_id` - B-tree index
- `score_lines.major_code` - B-tree index
- `score_lines.year` - B-tree index
- `recommendation_cache.params_hash` - UNIQUE index
- `recommendation_cache.profile_id` - B-tree index

## Static Data (code-level, not in DB)

| File | Content |
|------|---------|
| `app/data/school_levels.py` | Hardcoded sets of C9 (9), 985 (39), 211 (77+), 双一流 (12+) school 5-digit codes |
| `app/data/province_mapping.py` | GB/T 2260 province code mapping, SCHOOL_TO_PROVINCE lookup (80+ schools), NAME_PROVINCE_HINTS keyword matching (100+ cities) |

## Seeding Scripts

```
backend/scripts/
  add_2025_2026_scores.py              # Add fake score data for recent years
  add_cache_and_cards.py               # Seed recommendation cache
  add_detailed_professional_majors.py  # Add detailed major data
  add_exam_fields.py                   # Add exam subject fields
  add_preference_weights.py            # Seed preference weights
  expand_data.py                       # Expand school data
  fix_school_levels.py                 # Fix school level classifications
  fix_school_provinces.py              # Fix province assignments
  import_yantu_schools.py              # Import from yantu_schools.json
  seed_majors_and_scores.py            # Seed initial majors and score lines
```

## Test Database

- `backend/test_gradschool.db` -- Separate test database (used by pytest with conftest.py fixtures)
