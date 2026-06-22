"""
Decision service — orchestrates school/major recommendations.

Public API:
- recommend()            — full recommendation pipeline
- analyze_school_major() — single school + major analysis
- recommend_by_school_names() — fast recommendation from chat-extracted school names
- _generate_qualitative_analysis() — minimal LLM call for pros/cons (used by pipeline_agent)
"""

import hashlib
import json
import logging
import re
from datetime import date, timedelta

logger = logging.getLogger(__name__)

from sqlalchemy import select, or_, delete
from sqlalchemy.orm import Session

from app.models import School, Major, SchoolMajor, ScoreLine, UserProfile, RecommendationCache, SchoolCategory
from app.agents.orchestrator import orchestrator, DecisionResult, AnalyzeResult, RecommendationItem
from app.services.score_service import _analyze_trend as _analyze_trend_py
from app.services.scoring import (
    build_profile_dict,
    build_major_lookup,
    build_code_prefixes,
    build_exam_subjects_lookup,
    build_name_to_subjects,
    build_discipline_rating_lookup,
    build_recommendation_items,
    compute_recommendations,
)
from app.services.trends import build_trends_bulk, LEVEL_PRIORITY


# ── Shared helpers ────────────────────────────────────────────────────────────


def _build_ug_safety_entry(
    db: Session,
    profile: UserProfile,
    school_dicts: list[dict],
    score_dicts: list[dict],
    trends: list[dict],
    major_keyword: str,
    major_lookup: dict[str, dict],
    code_prefixes: dict | None,
    background_tier: str,
    discipline_rating_lookup: dict[str, int] | None,
) -> dict | None:
    """Build a 保底 recommendation entry for the user's undergraduate school.

    When no schools qualify as 保底 (safety), suggesting the user's own
    undergraduate school is a natural fallback — the student already has
    advantages there (familiarity, faculty connections, 本校保护 policies).
    """
    ug_name = (profile.undergraduate_school or "").strip()
    if not ug_name:
        return None

    ug_school = db.execute(
        select(School).where(
            School.name == ug_name,
            School.category == SchoolCategory.GRAD_EXAM,
        )
    ).scalar()
    if not ug_school:
        return None

    # Find a major offered by this school that matches the user's keyword
    ug_major_code = ""
    ug_major_name = major_keyword
    if major_keyword and major_keyword.strip():
        ug_majors = list(db.execute(
            select(Major).join(SchoolMajor).where(
                SchoolMajor.school_id == ug_school.id,
                or_(
                    Major.name.ilike(f"%{major_keyword}%"),
                    Major.discipline.ilike(f"%{major_keyword}%"),
                    Major.category.ilike(f"%{major_keyword}%"),
                )
            ).limit(5)
        ).scalars().all())
        if ug_majors:
            ug_major_code = ug_majors[0].code or ""
            ug_major_name = ug_majors[0].name
        else:
            return None
    else:
        # No major keyword; pick the first major this school offers
        first_sm = db.execute(
            select(Major).join(SchoolMajor).where(SchoolMajor.school_id == ug_school.id).limit(1)
        ).scalar()
        if first_sm:
            ug_major_code = first_sm.code or ""
            ug_major_name = first_sm.name
        else:
            return None

    # Get score lines for this school + major
    ug_scores = [sl for sl in score_dicts
                 if sl.get("school_id") == ug_school.id
                 and sl.get("major_code") == ug_major_code]
    re_scores = [sl.get("re_exam_total_score", 0) for sl in ug_scores if sl.get("re_exam_total_score")]
    scores = [sl.get("total_score", 0) for sl in ug_scores if sl.get("total_score")]

    # Compute cutoff
    from app.services.scoring import (
        normalize_score, score_major_keyword, _score_component,
        _tier_gap_penalty, _first_choice_bonus_from_admissions,
        TIER_DIFFICULTY_MULTIPLIER, TIER_RE_EXAM_PREMIUM,
        INSTITUTE_TIER_MULTIPLIER, MAJOR_DIFFICULTY_BONUS,
        _SCORE_TO_RATING, is_research_institute, RATING_TO_SCORE,
    )

    school_level = ug_school.level.value if ug_school.level else ""
    is_inst = is_research_institute(ug_school.name)
    recent_scores = sorted(scores)[-3:] if len(scores) >= 3 else scores
    recent_avg = sum(recent_scores) / len(recent_scores) if recent_scores else 0

    if re_scores:
        base_avg = sum(re_scores) / len(re_scores)
    elif recent_avg > 0:
        premium = TIER_RE_EXAM_PREMIUM.get(school_level, 0)
        base_avg = recent_avg + premium
    elif scores:
        base_avg = sum(scores) / len(scores)
    else:
        base_avg = 0

    tier_mult = INSTITUTE_TIER_MULTIPLIER if is_inst else TIER_DIFFICULTY_MULTIPLIER.get(school_level, 1.0)

    # Program-difficulty bonus
    if discipline_rating_lookup and ug_school.name in discipline_rating_lookup:
        rating_score = discipline_rating_lookup[ug_school.name]
        rating_label = _SCORE_TO_RATING.get(rating_score, "")
        prog_diff_bonus = MAJOR_DIFFICULTY_BONUS.get(rating_label, 0.0)
    else:
        prog_diff_bonus = 0.0

    effective_cutoff = base_avg * (tier_mult + prog_diff_bonus) if base_avg > 0 else 0

    # Risk classification (background-aware)
    estimated = profile.estimated_score or 0
    exam_config = {}
    if profile.exam_config:
        import json as _json
        try:
            exam_config = _json.loads(profile.exam_config)
        except (_json.JSONDecodeError, TypeError):
            pass
    estimated = normalize_score(estimated, exam_config)

    from app.services.scoring import _background_risk_shift
    risk_shift = _background_risk_shift(background_tier, school_level)
    if estimated > 0 and effective_cutoff > 0:
        risk_diff = estimated - effective_cutoff + risk_shift
        if risk_diff > 15:
            risk = "保底"
        elif risk_diff < -15:
            risk = "冲刺"
        else:
            risk = "稳妥"
    else:
        risk = "稳妥"

    if risk not in ("保底", "稳妥"):
        return None

    # Compute school_match with new 6-factor formula
    from app.services.scoring import get_dual_non_penalty

    score_fit_val = _score_component(estimated, effective_cutoff)

    major_strength = 50
    if discipline_rating_lookup:
        major_strength = discipline_rating_lookup.get(ug_school.name, 50)

    dual_penalty = get_dual_non_penalty(ug_school.name, school_level, background_tier)
    fc_bonus = _first_choice_bonus_from_admissions(ug_school.name, school_level)
    background_fit = max(20, min(100, 70 + dual_penalty + fc_bonus))

    if profile.target_province and ug_school.province == profile.target_province:
        region_fit = 100
    elif profile.target_province:
        region_fit = 60
    else:
        region_fit = 70

    if profile.target_level and school_level == profile.target_level:
        level_fit = 100
    elif profile.target_level:
        level_fit = 60
    else:
        level_fit = 70

    # Default weights for 本校保底
    w_score_fit = 0.6
    w_program = 0.6
    w_background = 0.5
    w_region = 0.5
    w_level = 0.5
    factor_total = w_score_fit + w_program + w_background + w_region + w_level
    school_match = int(
        (score_fit_val * w_score_fit
         + major_strength * w_program
         + background_fit * w_background
         + region_fit * w_region
         + level_fit * w_level)
        / factor_total
    )

    tier_penalty = _tier_gap_penalty(background_tier, school_level)
    school_match = max(10, min(100, school_match - tier_penalty))
    school_match = max(5, school_match + dual_penalty)

    # Major match score
    if major_keyword and major_keyword.strip():
        mdata = major_lookup.get(ug_major_name)
        if mdata:
            major_score = score_major_keyword(
                major_keyword, mdata.get("name", ug_major_name),
                mdata.get("first_level", ""), mdata.get("category", ""),
                major_code=mdata.get("code", ""), code_prefixes=code_prefixes,
            )
        else:
            major_score = 5
    else:
        major_score = 50

    final_match = int(school_match * 0.55 + major_score * 0.45)
    final_match = min(100, max(5, final_match))

    # Trend / competition
    trend_text = ""
    for t in trends:
        if t.get("school_name") == ug_school.name and t.get("major_name") == ug_major_name:
            trend_text = t.get("trend_analysis", "")
            break

    # Build precomputed entry
    return {
        "school_name": ug_school.name,
        "school_province": ug_school.province or "",
        "school_level": school_level,
        "school_type": ug_school.school_type.value if ug_school.school_type else "",
        "school_description": (ug_school.description or "")[:200],
        "ranking_national": ug_school.ranking_national,
        "major_name": ug_major_name,
        "major_code": ug_major_code,
        "risk_level": risk,
        "match_score": final_match,
        "score_trend": trend_text,
        "competition": "本校报考",
        "recent_avg_score": int(primary_avg) if primary_avg else 0,
        "re_exam_avg_score": int(base_avg) if base_avg else 0,
        "normalized_score": estimated,
        "subject_warnings": [],
        "major_match_level": "related",
        "is_research_institute": is_inst,
        "major_strength_score": major_strength,
        "major_strength_label": "",
        "admissions_summary": "本校报考：熟悉环境、联系导师便利，复试有天然优势",
    }


# ── Original helpers ─────────────────────────────────────────────────────────

def _extract_json(content: str) -> dict | None:
    """Extract the first valid JSON object from LLM response text.

    Tries direct parse first, then from the last '{' (LLMs often put JSON last),
    then falls back to greedy regex. Returns None if nothing parses.
    """
    if not content:
        return None
    content = content.strip()
    try:
        return json.loads(content)
    except (json.JSONDecodeError, TypeError):
        pass
    last_open = content.rfind('{')
    if last_open >= 0:
        try:
            return json.loads(content[last_open:])
        except json.JSONDecodeError:
            pass
    match = re.search(r"\{[\s\S]*\}", content)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return None


def _resolve_profile_defaults(
    profile: UserProfile,
    target_province: str | None,
    target_level: str | None,
    target_major_keyword: str | None,
) -> tuple[str | None, str | None, str]:
    """Resolve province/level/major from API params, preference_weights, and profile."""
    pw: dict = {}
    try:
        if profile.preference_weights:
            pw = json.loads(profile.preference_weights)
    except (json.JSONDecodeError, TypeError):
        pass
    pw_cities: list[str] = pw.get("preferred_cities", []) or []
    pw_majors: list[str] = pw.get("preferred_majors", []) or []

    province = target_province or (pw_cities[0] if pw_cities else None) or profile.target_province
    level = target_level if target_level is not None else (None if pw else profile.target_level)
    major_keyword = target_major_keyword or (pw_majors[0] if pw_majors else "") or profile.undergraduate_major or ""

    return province, level, major_keyword


def _build_school_dicts(schools: list[School]) -> list[dict]:
    return [
        {
            "id": s.id,
            "name": s.name,
            "province": s.province,
            "city": s.city or "",
            "level": s.level.value if s.level else "",
            "school_type": s.school_type.value if s.school_type else "",
            "description": s.description,
            "ranking_national": s.ranking_national,
        }
        for s in schools
    ]


def _build_score_dicts(score_lines: list[ScoreLine]) -> list[dict]:
    return [
        {
            "id": sl.id,
            "school_id": sl.school_id,
            "major_code": sl.major_code,
            "year": sl.year,
            "total_score": sl.total_score,
            "category": sl.category,
            "applicant_count": sl.applicant_count,
            "admit_count": sl.admit_count,
            "re_exam_total_score": sl.re_exam_total_score,
        }
        for sl in score_lines
    ]


def _build_result_json(recommendations: list[RecommendationItem],
                       analysis_text: dict,
                       name_to_subjects: dict[tuple[str, str], list[str]]) -> str:
    return json.dumps({
        "recommendations": [
            {
                "school_name": r.school_name,
                "school_province": r.school_province,
                "school_level": r.school_level,
                "school_type": r.school_type,
                "school_description": r.school_description,
                "ranking_national": r.ranking_national,
                "major_name": r.major_name,
                "major_code": r.major_code,
                "risk_level": r.risk_level,
                "match_score": r.match_score,
                "score_trend": r.score_trend,
                "competition": r.competition,
                "re_exam_avg_score": r.re_exam_avg_score,
                "pros": r.pros,
                "cons": r.cons,
                "subject_warnings": r.subject_warnings,
                "major_match_level": r.major_match_level,
                "is_research_institute": r.is_research_institute,
                "major_strength_score": r.major_strength_score,
                "major_strength_label": r.major_strength_label,
                "admissions_summary": r.admissions_summary,
            }
            for r in recommendations
        ],
        "analysis": analysis_text.get("analysis", "") if isinstance(analysis_text, dict) else "",
        "plan_suggestion": analysis_text.get("plan_suggestion", "") if isinstance(analysis_text, dict) else "",
        "exam_subjects": {f"{k[0]}|{k[1]}": v for k, v in name_to_subjects.items()},
    }, ensure_ascii=False)


async def _run_pipeline(
    db: Session,
    profile: UserProfile,
    schools: list[School],
    province: str | None,
    level: str | None,
    major_keyword: str,
    params_hash: str,
    no_results_msg: str = "暂无匹配的院校专业数据，请扩大搜索范围。",
) -> tuple[DecisionResult, dict]:
    """Shared pipeline: score → LLM → cache → result.

    Both recommend() and recommend_by_school_names() use this after matching schools.
    """
    if not schools:
        return DecisionResult(
            recommendations=[], analysis=no_results_msg,
            plan_suggestion="", raw_text="",
        ), {}

    school_ids = [s.id for s in schools]

    score_lines = list(
        db.execute(
            select(ScoreLine)
            .where(ScoreLine.school_id.in_(school_ids))
            .order_by(ScoreLine.year.desc())
        ).scalars().all()
    )

    trends = build_trends_bulk(db, score_lines, schools)
    school_dicts = _build_school_dicts(schools)
    score_dicts = _build_score_dicts(score_lines)
    profile_dict = build_profile_dict(profile, province or "", level or "")

    major_lookup = build_major_lookup(db, major_keyword)

    code_prefixes = build_code_prefixes(db, major_keyword)
    discipline_rating_lookup = build_discipline_rating_lookup(db, code_prefixes)

    major_keys = set((sl.school_id, sl.major_code) for sl in score_lines)
    exam_subjects_lookup = build_exam_subjects_lookup(db, major_keys)
    name_to_subjects = build_name_to_subjects(exam_subjects_lookup, schools)

    # Look up undergraduate school tier for background gap penalty
    background_tier = ""
    if profile.undergraduate_school:
        ug_school = db.execute(
            select(School).where(School.name == profile.undergraduate_school)
        ).scalar()
        if ug_school and ug_school.level:
            background_tier = ug_school.level.value

    # Map risk_tolerance → risk_direction for distribution rebalancing
    _risk_tolerance = (profile.preference_weights or "").strip()
    _risk_map = {"保守": "保底", "激进": "冲刺", "适中": ""}
    risk_direction = ""
    try:
        pw = json.loads(profile.preference_weights or "{}")
        rt = pw.get("risk_tolerance", "")
        risk_direction = _risk_map.get(rt, "")
    except (json.JSONDecodeError, TypeError):
        pass

    precomputed = compute_recommendations(
        profile_dict, school_dicts, score_dicts, trends,
        major_keyword=major_keyword, major_lookup=major_lookup,
        name_to_subjects=name_to_subjects,
        code_prefixes=code_prefixes,
        background_tier=background_tier,
        discipline_rating_lookup=discipline_rating_lookup,
        risk_direction=risk_direction,
    )

    # ── 本校保底: when no 保底 schools found, try undergraduate school ──
    if not any(r["risk_level"] == "保底" for r in precomputed):
        ug_entry = _build_ug_safety_entry(
            db, profile, school_dicts, score_dicts, trends,
            major_keyword, major_lookup, code_prefixes,
            background_tier, discipline_rating_lookup,
        )
        if ug_entry:
            precomputed.append(ug_entry)
            # Re-apply risk distribution with the new entry
            from app.services.scoring import _rebalance_risk_distribution
            precomputed = _rebalance_risk_distribution(precomputed, risk_direction, top_n=8)

    if not precomputed:
        return DecisionResult(
            recommendations=[], analysis=no_results_msg,
            plan_suggestion="", raw_text="",
        ), {}

    try:
        analysis_text = await _generate_qualitative_analysis(profile_dict, precomputed)
    except Exception:
        logger.warning("Qualitative analysis failed, using rule-based scoring only", exc_info=True)
        analysis_text = {}

    pros_by_idx = analysis_text.get("pros_by_idx", {}) if isinstance(analysis_text, dict) else {}
    recommendations = build_recommendation_items(precomputed, pros_by_idx)

    # Save to cache
    result_json = _build_result_json(recommendations, analysis_text, name_to_subjects)
    try:
        db.execute(
            delete(RecommendationCache).where(
                RecommendationCache.profile_id == profile.id,
                RecommendationCache.params_hash == params_hash,
            )
        )
        cache_entry = RecommendationCache(
            profile_id=profile.id,
            params_hash=params_hash,
            result_json=result_json,
            created_at=date.today(),
        )
        db.add(cache_entry)
        db.commit()
    except Exception:
        db.rollback()
        logger.warning("Failed to write recommendation cache", exc_info=True)

    return DecisionResult(
        recommendations=recommendations,
        analysis=analysis_text.get("analysis", "") if isinstance(analysis_text, dict) else "",
        plan_suggestion=analysis_text.get("plan_suggestion", "") if isinstance(analysis_text, dict) else "",
        raw_text="",
    ), name_to_subjects


# ── Public API ────────────────────────────────────────────────────────────────

async def recommend(
    db: Session,
    profile_id: int,
    target_province: str | None = None,
    target_level: str | None = None,
    target_major_keyword: str | None = None,
) -> tuple[DecisionResult, dict]:
    """Orchestrate recommendation with pre-computation + small LLM call."""

    profile = db.get(UserProfile, profile_id)
    if not profile:
        return DecisionResult(
            recommendations=[], analysis="未找到考生画像，请先创建个人资料。",
            plan_suggestion="", raw_text="",
        ), {}

    province, level, major_keyword = _resolve_profile_defaults(
        profile, target_province, target_level, target_major_keyword,
    )

    # Check recommendation cache (7-day validity).
    # Include all scoring-relevant profile fields so cache invalidates on profile update.
    pw_hash = hashlib.sha256((profile.preference_weights or "").encode()).hexdigest()[:16]
    profile_fingerprint = hashlib.sha256(
        f"{profile.estimated_score}|{profile.undergraduate_school or ''}|"
        f"{profile.undergraduate_major or ''}|{profile.exam_config or ''}"
        .encode()
    ).hexdigest()[:12]
    cache_key = (
        f"{profile_id}|{province or ''}|{level or ''}|{major_keyword}|{pw_hash}"
        f"|{profile_fingerprint}"
    )
    params_hash = hashlib.sha256(cache_key.encode()).hexdigest()
    cache_entry = db.execute(
        select(RecommendationCache).where(
            RecommendationCache.profile_id == profile_id,
            RecommendationCache.params_hash == params_hash,
            RecommendationCache.created_at >= date.today() - timedelta(days=7),
        )
    ).scalar()
    if cache_entry:
        try:
            cached = json.loads(cache_entry.result_json)
            recommendations = [
                RecommendationItem(**r) for r in cached.get("recommendations", [])
            ]
            exam_subjects_map = {
                tuple(k): v for k, v in cached.get("exam_subjects", {}).items()
            }
            return DecisionResult(
                recommendations=recommendations,
                analysis=cached.get("analysis", ""),
                plan_suggestion=cached.get("plan_suggestion", ""),
                raw_text="",
            ), exam_subjects_map
        except (json.JSONDecodeError, TypeError):
            pass

    # Match schools by province/level. Only 考研高校 (grad-exam eligible).
    # When no level filter, fetch a larger pool so tier diversity rebalancing
    # has enough schools from every tier to work with.
    stmt = select(School).where(School.category == SchoolCategory.GRAD_EXAM)
    if province:
        stmt = stmt.where(or_(School.province == province, School.city == province))
    if level:
        stmt = stmt.where(School.level == level)
    stmt = stmt.order_by(School.ranking_national.asc().nulls_last()).limit(60 if not level else 15)
    schools = list(db.execute(stmt).scalars().all())

    # Fallbacks (keep province, then keep level, then drop all)
    if not schools:
        stmt = select(School).where(School.category == SchoolCategory.GRAD_EXAM)
        if province:
            stmt = stmt.where(or_(School.province == province, School.city == province))
        stmt = stmt.order_by(School.ranking_national.asc().nulls_last()).limit(15)
        schools = list(db.execute(stmt).scalars().all())

    if not schools:
        stmt = select(School).where(School.category == SchoolCategory.GRAD_EXAM)
        if level:
            stmt = stmt.where(School.level == level)
        stmt = stmt.order_by(School.ranking_national.asc().nulls_last()).limit(10)
        schools = list(db.execute(stmt).scalars().all())

    if not schools:
        stmt = select(School).where(School.category == SchoolCategory.GRAD_EXAM)
        stmt = stmt.order_by(School.ranking_national.asc().nulls_last()).limit(10)
        schools = list(db.execute(stmt).scalars().all())

    # Major keyword search — expand school pool
    major_lookup: dict[str, dict] = {}
    school_match_count: dict[int, int] = {}
    if major_keyword and major_keyword.strip():
        kw = major_keyword.strip()
        matching_rows = list(
            db.execute(
                select(SchoolMajor.school_id, Major)
                .join(Major, SchoolMajor.major_id == Major.id)
                .where(
                    or_(
                        Major.name.ilike(f"%{kw}%"),
                        Major.discipline.ilike(f"%{kw}%"),
                        Major.category.ilike(f"%{kw}%"),
                    )
                ).limit(500)
            ).all()
        )

        if not matching_rows:
            parts = re.split(r"[与和及、，,]", kw)
            parts = [p.strip() for p in parts if len(p.strip()) >= 2]
            if parts:
                conditions = []
                for part in parts:
                    conditions.append(Major.name.ilike(f"%{part}%"))
                    conditions.append(Major.discipline.ilike(f"%{part}%"))
                    conditions.append(Major.category.ilike(f"%{part}%"))
                matching_rows = list(
                    db.execute(
                        select(SchoolMajor.school_id, Major)
                        .join(Major, SchoolMajor.major_id == Major.id)
                        .where(or_(*conditions)).limit(500)
                    ).all()
                )

        if matching_rows:
            seen_schools: set[int] = set()
            for school_id, m in matching_rows:
                seen_schools.add(school_id)
                school_match_count[school_id] = school_match_count.get(school_id, 0) + 1
                if m.name not in major_lookup:
                    major_lookup[m.name] = {
                        "name": m.name,
                        "first_level": m.discipline or "",
                        "category": m.category or "",
                        "code": m.code,
                        "degree_level": m.degree_type or "",
                    }
            existing_ids = {s.id for s in schools}
            major_school_ids = [sid for sid in seen_schools if sid not in existing_ids]
            if major_school_ids:
                extra_schools = list(
                    db.execute(
                        select(School)
                        .where(
                            School.id.in_(major_school_ids[:400]),
                            School.category == SchoolCategory.GRAD_EXAM,
                        )
                        .order_by(School.ranking_national.asc().nulls_last())
                        .limit(15)
                    ).scalars().all()
                )
                schools.extend(extra_schools)
    else:
        major_keyword = ""

    # Ensure tier diversity when no level preference (avoid all top-school results).
    # Within each tier, sort by major-keyword match count (desc) so schools that
    # actually offer the user's target major float to the top, regardless of their
    # national ranking relative to comprehensive universities.
    if not level and len(schools) > 6:
        tiers: dict[str, list[School]] = {"top": [], "mid": [], "other": []}
        for s in schools:
            lv = s.level.value if s.level else ""
            if lv in ("C9", "985"):
                tiers["top"].append(s)
            elif lv == "211":
                tiers["mid"].append(s)
            else:
                tiers["other"].append(s)

        def _tier_sort_key(s: School) -> tuple[int, int]:
            matches = school_match_count.get(s.id, 0)
            rank = s.ranking_national or 9999
            return (-matches, rank)

        for tier_name in tiers:
            tiers[tier_name].sort(key=_tier_sort_key)

        schools = tiers["top"][:6] + tiers["mid"][:8] + tiers["other"][:4]

    # Cap school pool
    if len(schools) > 30:
        schools.sort(key=lambda s: s.ranking_national or 9999)
        schools = schools[:30]

    return await _run_pipeline(
        db, profile, schools, province, level, major_keyword, params_hash,
    )


async def recommend_by_school_names(
    db: Session,
    profile_id: int,
    school_names: list[str],
    target_province: str | None = None,
    target_level: str | None = None,
    target_major_keyword: str | None = None,
) -> tuple[DecisionResult, dict]:
    """Fast recommendation from school names extracted from chat.

    Fuzzy-matches school names, sorts by ranking quality, then runs the shared pipeline.
    """
    profile = db.get(UserProfile, profile_id)
    if not profile:
        return DecisionResult(
            recommendations=[], analysis="未找到考生画像，请先创建个人资料。",
            plan_suggestion="", raw_text="",
        ), {}

    if not school_names:
        return DecisionResult(
            recommendations=[], analysis="未从对话中提取到学校名称。",
            plan_suggestion="", raw_text="",
        ), {}

    conditions = [School.name.ilike(f"%{n}%") for n in school_names[:10]]
    matched = list(db.execute(
        select(School).where(or_(*conditions)).limit(100)
    ).scalars().all())

    if not matched:
        return await recommend(
            db, profile_id, target_province, target_level, target_major_keyword
        )

    def _sort_key(s: School) -> tuple[int, int]:
        level_str = s.level.value if s.level else ""
        lp = LEVEL_PRIORITY.get(level_str, 99)
        rank = s.ranking_national if s.ranking_national else 9999
        return (lp, rank)

    matched.sort(key=_sort_key)
    schools = matched[:10]

    province, level, major_keyword = _resolve_profile_defaults(
        profile, target_province, target_level, target_major_keyword,
    )

    pw_hash = hashlib.sha256((profile.preference_weights or "").encode()).hexdigest()[:16]
    profile_fingerprint = hashlib.sha256(
        f"{profile.estimated_score}|{profile.undergraduate_school or ''}|"
        f"{profile.undergraduate_major or ''}|{profile.exam_config or ''}"
        .encode()
    ).hexdigest()[:12]
    source_tag = f"chat:{','.join(school_names[:5])}"
    cache_key = (
        f"{profile_id}|{province or ''}|{level or ''}|{major_keyword}"
        f"|{pw_hash}|{profile_fingerprint}|{source_tag}"
    )
    params_hash = hashlib.sha256(cache_key.encode()).hexdigest()

    return await _run_pipeline(
        db, profile, schools, province, level, major_keyword, params_hash,
        no_results_msg="该学校暂无足够分数线数据，请尝试扩大搜索。",
    )


def get_school_info_by_names(
    db: Session,
    school_names: list[str],
) -> list[dict]:
    """Lightweight school info lookup by name — no scoring pipeline.

    Returns basic school data + available majors for chat inline cards.
    """
    if not school_names:
        return []

    conditions = [School.name.ilike(f"%{n}%") for n in school_names[:10]]
    schools = list(db.execute(
        select(School).where(or_(*conditions)).limit(20)
    ).scalars().all())

    if not schools:
        return []

    school_ids = [s.id for s in schools]
    school_majors = list(db.execute(
        select(SchoolMajor).where(SchoolMajor.school_id.in_(school_ids)).limit(200)
    ).scalars().all())

    major_ids = list({sm.major_id for sm in school_majors if sm.major_id})
    majors_map: dict[int, Major] = {}
    if major_ids:
        majors = list(db.execute(
            select(Major).where(Major.id.in_(major_ids))
        ).scalars().all())
        majors_map = {m.id: m for m in majors}

    # Group majors by school
    school_majors_map: dict[int, list[dict]] = {}
    for sm in school_majors:
        major = majors_map.get(sm.major_id)
        if not major:
            continue
        entry = {
            "major_name": major.name,
            "major_code": major.code,
            "department": sm.department,
            "direction": sm.direction,
            "study_mode": sm.study_mode,
            "planned_enrollment": sm.planned_enrollment,
            "exam_subjects": [s for s in [
                sm.exam_politics, sm.exam_english, sm.exam_math,
                sm.exam_course1_name, sm.exam_course2_name, sm.exam_course3_name,
            ] if s],
        }
        school_majors_map.setdefault(sm.school_id, []).append(entry)

    def _level_label(s: School) -> str:
        if s.is_985:
            return "985"
        if s.is_211:
            return "211"
        if s.is_double_first:
            return "双一流"
        return s.level.value if s.level else "普本"

    result: list[dict] = []
    for s in schools:
        majors = school_majors_map.get(s.id, [])
        result.append({
            "school_name": s.name,
            "school_province": s.province or "",
            "school_level": _level_label(s),
            "school_type": s.school_type.value if s.school_type else "",
            "school_description": s.description or "",
            "ranking_national": s.ranking_national,
            "is_985": s.is_985,
            "is_211": s.is_211,
            "is_double_first": s.is_double_first,
            "majors": majors[:10],
            "majors_count": len(majors),
        })

    # Sort by ranking quality
    def _sort_key(item: dict) -> tuple[int, int]:
        lp = LEVEL_PRIORITY.get(item["school_level"], 99)
        rank = item["ranking_national"] or 9999
        return (lp, rank)

    result.sort(key=_sort_key)
    return result


# ── Qualitative analysis (LLM) ──────────────────────────────────────────────

async def _generate_qualitative_analysis(
    profile: dict,
    precomputed: list[dict],
) -> dict:
    """Minimal LLM call — generates per-item pros/cons by index (unambiguous).

    Returns {"pros_by_idx": {1: {"pros":[],"cons":[]}, ...}, "analysis": str, "plan_suggestion": str}
    """
    summary_lines = []
    for i, r in enumerate(precomputed[:8], 1):
        summary_lines.append(
            f"#{i} {r['school_name']} | {r['major_name']} | "
            f"层次:{r['school_level']} | 省份:{r['school_province']} | "
            f"风险:{r['risk_level']} | 匹配分:{r['match_score']} | "
            f"竞争:{r['competition']} | "
            f"招录特征:{r.get('admissions_summary', '')}"
        )

    compact_prompt = f"""考生: 预估{profile.get('estimated_score', '未知')}分, 目标{profile.get('target_province', '不限')}, 层次{profile.get('target_level', '不限')}

预计算结果:
{chr(10).join(summary_lines)}

请为以上每个#编号的院校返回pros和cons，用index字段对应编号。仅返回JSON:
{{"items":[{{"index":1,"pros":["优势"],"cons":["劣势"]}}],"analysis":"整体分析(150字内)","plan_suggestion":"备考建议(100字内)"}}"""

    try:
        resp = await orchestrator.client.chat.completions.create(
            model=orchestrator.model,
            messages=[
                {"role": "system", "content": "你是考研择校顾问。根据预计算结果为每个院校生成pros/cons。注意利用招录特征字段：复试占比高(≥50%)标注为风险(cons)，保护一志愿和不歧视双非标注为优势(pros)，不保护一志愿或歧视双非标注为劣势(cons)。仅返回JSON，用index对应编号而非校名。"},
                {"role": "user", "content": compact_prompt},
            ],
            temperature=0.4,
            max_tokens=600,
        )

        content = resp.choices[0].message.content or "{}"

        data = _extract_json(content)
        if data is None:
            return {"pros_by_idx": {}, "analysis": "", "plan_suggestion": ""}

        items = data.get("items", [])
        pros_by_idx: dict[int, dict] = {}
        for item in items:
            idx = item.get("index", 0)
            if isinstance(idx, int) and 1 <= idx <= len(precomputed):
                pros_by_idx[idx] = {"pros": item.get("pros", []), "cons": item.get("cons", [])}

        return {
            "analysis": data.get("analysis", ""),
            "plan_suggestion": data.get("plan_suggestion", ""),
            "pros_by_idx": pros_by_idx,
        }
    except Exception:
        return {"pros_by_idx": {}, "analysis": "", "plan_suggestion": ""}


# ── Single school + major analysis ──────────────────────────────────────────

async def analyze_school_major(
    db: Session,
    school_id: int,
    major_code: str,
    estimated_score: int | None = None,
) -> AnalyzeResult:
    """Analyze a specific school + major combination."""
    school = db.get(School, school_id)
    if not school:
        return AnalyzeResult(
            risk_level="未知", match_score=0, score_trend="",
            competition="", pros=[], cons=[],
            analysis="未找到该院校", preparation_tips="", raw_text="",
        )

    # Look up major via SchoolMajor junction
    sm = db.execute(
        select(SchoolMajor).where(
            SchoolMajor.school_id == school_id
        ).where(SchoolMajor.major.has(Major.code == major_code))
    ).scalar()
    major = db.get(Major, sm.major_id) if sm else None
    if not major:
        major = db.execute(
            select(Major).where(Major.code == major_code)
        ).scalar()

    score_lines = list(
        db.execute(
            select(ScoreLine)
            .where(ScoreLine.school_id == school_id, ScoreLine.major_code == major_code)
            .order_by(ScoreLine.year.desc())
        ).scalars().all()
    )

    school_dict = {
        "name": school.name,
        "province": school.province,
        "level": school.level.value if school.level else "",
        "school_type": school.school_type.value if school.school_type else "",
        "description": school.description,
    }

    major_dict = {
        "name": major.name if major else major_code,
        "code": major_code,
        "degree_level": major.degree_type if major else "",
        "exam_subjects": "",
    }

    # Pre-compute risk level and match score in Python
    scores = [sl.total_score for sl in score_lines if sl.total_score]
    if scores and estimated_score:
        recent_avg = sum(scores[-3:]) / len(scores[-3:]) if scores[-3:] else sum(scores) / len(scores)
        diff = estimated_score - recent_avg
        risk_level = "保底" if diff > 15 else "冲刺" if diff < -15 else "稳妥"
    else:
        risk_level = "未知"
        diff = 0

    # Compute competition from data
    ratios = []
    for sl in score_lines:
        if sl.applicant_count and sl.admit_count and sl.applicant_count > 0:
            ratios.append(sl.admit_count / sl.applicant_count)
    avg_ratio = sum(ratios) / len(ratios) if ratios else 0
    if avg_ratio > 0 and avg_ratio < 0.1:
        competition = "竞争激烈"
    elif 0.1 <= avg_ratio < 0.2:
        competition = "竞争较激烈"
    else:
        competition = "竞争中等"

    trend_text = _analyze_trend_py(sorted(score_lines, key=lambda x: x.year))

    try:
        compact_prompt = json.dumps({
            "院校": school_dict["name"],
            "层次": school_dict["level"],
            "省份": school_dict["province"],
            "专业": major_dict["name"],
            "预估分数": estimated_score or "未知",
            "预计算风险": risk_level,
            "预计算竞争": competition,
            "趋势": trend_text[:100],
        }, ensure_ascii=False)

        resp = await orchestrator.client.chat.completions.create(
            model=orchestrator.model,
            messages=[
                {"role": "system", "content": "你是考研择校顾问。基于预计算结果，用JSON返回：pros(字符串数组,2-4条)、cons(字符串数组,1-3条)、analysis(150字内)、preparation_tips(100字内)。仅返回JSON。"},
                {"role": "user", "content": compact_prompt + "\n\n请给出该院校+专业的分析。"},
            ],
            temperature=0.4,
            max_tokens=500,
        )

        content = resp.choices[0].message.content or "{}"
        llm_data = _extract_json(content) or {}

        return AnalyzeResult(
            risk_level=risk_level,
            match_score=int(max(0, min(100, 50 + diff // 2))) if estimated_score else 50,
            score_trend=trend_text,
            competition=competition,
            pros=llm_data.get("pros", []),
            cons=llm_data.get("cons", []),
            analysis=llm_data.get("analysis", ""),
            preparation_tips=llm_data.get("preparation_tips", ""),
            raw_text="",
        )
    except Exception:
        return AnalyzeResult(
            risk_level=risk_level,
            match_score=int(max(0, min(100, 50 + diff // 2))) if estimated_score else 50,
            score_trend=trend_text,
            competition=competition,
            pros=[], cons=[],
            analysis="", preparation_tips="",
            raw_text="",
        )
