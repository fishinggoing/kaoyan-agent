"""School-major enrollment data service — replaces old score-line queries."""

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models import SchoolMajor, School, Major, ScoreLine


def list_school_majors(
    db: Session,
    school_id: int | None = None,
    major_id: int | None = None,
    year: int | None = None,
    page: int = 1,
    size: int = 20,
) -> tuple[list[dict], int]:
    stmt = select(SchoolMajor)
    if school_id:
        stmt = stmt.where(SchoolMajor.school_id == school_id)
    if major_id:
        stmt = stmt.where(SchoolMajor.major_id == major_id)
    if year:
        stmt = stmt.where(SchoolMajor.year == year)

    count = db.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0
    stmt = stmt.order_by(SchoolMajor.planned_enrollment.desc().nullslast())
    stmt = stmt.offset((page - 1) * size).limit(size)
    items = db.execute(stmt).scalars().all()

    school_ids = {sm.school_id for sm in items}
    major_ids = {sm.major_id for sm in items}
    schools = {s.id: s for s in db.execute(select(School).where(School.id.in_(school_ids))).scalars()}
    majors = {m.id: m for m in db.execute(select(Major).where(Major.id.in_(major_ids))).scalars()}

    result = []
    for sm in items:
        s = schools.get(sm.school_id)
        m = majors.get(sm.major_id)
        result.append({
            "id": sm.id,
            "school_id": sm.school_id,
            "school_name": s.name if s else "",
            "school_level": s.level.value if s and s.level else "",
            "school_province": s.province if s else "",
            "major_id": sm.major_id,
            "major_code": m.code if m else "",
            "major_name": m.name if m else "",
            "major_category": m.category if m else "",
            "major_discipline": m.discipline if m else "",
            "degree_type": m.degree_type if m else "",
            "department": sm.department,
            "direction": sm.direction,
            "study_mode": sm.study_mode,
            "planned_enrollment": sm.planned_enrollment,
            "push_free_count": sm.push_free_count,
            "year": sm.year,
            "exam_politics": sm.exam_politics,
            "exam_english": sm.exam_english,
            "exam_math": sm.exam_math,
            "exam_course1_name": sm.exam_course1_name,
            "exam_course1_code": sm.exam_course1_code,
            "exam_course2_name": sm.exam_course2_name,
            "exam_course2_code": sm.exam_course2_code,
            "exam_course3_name": sm.exam_course3_name,
            "exam_course3_code": sm.exam_course3_code,
        })

    return result, count


def get_school_major_detail(db: Session, school_major_id: int) -> dict | None:
    sm = db.get(SchoolMajor, school_major_id)
    if not sm:
        return None
    s = db.get(School, sm.school_id)
    m = db.get(Major, sm.major_id)
    return {
        "id": sm.id,
        "school_id": sm.school_id,
        "school_name": s.name if s else "",
        "school_province": s.province if s else "",
        "school_level": s.level.value if s and s.level else "",
        "major_id": sm.major_id,
        "major_code": m.code if m else "",
        "major_name": m.name if m else "",
        "major_category": m.category if m else "",
        "major_discipline": m.discipline if m else "",
        "degree_type": m.degree_type if m else "",
        "department": sm.department,
        "direction": sm.direction,
        "study_mode": sm.study_mode,
        "planned_enrollment": sm.planned_enrollment,
        "push_free_count": sm.push_free_count,
        "year": sm.year,
        "exam_politics": sm.exam_politics,
        "exam_english": sm.exam_english,
        "exam_math": sm.exam_math,
        "exam_course1_name": sm.exam_course1_name,
        "exam_course1_code": sm.exam_course1_code,
        "exam_course2_name": sm.exam_course2_name,
        "exam_course2_code": sm.exam_course2_code,
        "exam_course3_name": sm.exam_course3_name,
        "exam_course3_code": sm.exam_course3_code,
        "data_source": sm.data_source,
    }


def get_school_enrollment_summary(db: Session, school_id: int) -> dict:
    """Aggregate enrollment stats for a school."""
    stmt = select(SchoolMajor).where(SchoolMajor.school_id == school_id)
    items = db.execute(stmt).scalars().all()

    total_slots = sum(sm.planned_enrollment or 0 for sm in items)
    total_push_free = sum(sm.push_free_count or 0 for sm in items)
    zero_enrollment = sum(1 for sm in items if sm.planned_enrollment == 0)
    has_enrollment = sum(1 for sm in items if (sm.planned_enrollment or 0) > 0)

    return {
        "school_id": school_id,
        "total_majors": len(items),
        "total_planned_enrollment": total_slots,
        "total_push_free": total_push_free,
        "majors_not_enrolling": zero_enrollment,
        "majors_enrolling": has_enrollment,
    }


def _analyze_trend(data_points: list) -> str:
    """Legacy trend analysis for compatibility with decision_service."""
    if not data_points or len(data_points) < 2:
        return "数据点不足，无法进行趋势分析。需要至少2年数据。"

    scores = [dp.total_score for dp in data_points if hasattr(dp, 'total_score') and dp.total_score]
    if len(scores) < 2:
        return "数据点不足，无法进行趋势分析。需要至少2年数据。"

    changes = [scores[i] - scores[i - 1] for i in range(1, len(scores))]
    avg_change = sum(changes) / len(changes)
    volatility = (max(scores) - min(scores)) / (sum(scores) / len(scores)) * 100 if sum(scores) > 0 else 0

    direction = "上升" if avg_change > 0 else "下降" if avg_change < 0 else "稳定"
    vol_desc = "波动较大" if volatility > 10 else "小幅波动" if volatility > 5 else "非常稳定"

    years = [dp.year for dp in data_points if hasattr(dp, 'year')]
    parts = [
        f"近{len(scores)}年（{years[0]}-{years[-1]}）总分呈{direction}趋势，{vol_desc}（波动率{volatility:.1f}%）。",
        f"年均变化约{avg_change:+.1f}分。",
    ]

    if len(scores) >= 3:
        recent_avg = sum(scores[-3:]) / 3
        older_avg = sum(scores[:-3]) / len(scores[:-3]) if len(scores) > 3 else scores[0]
        if recent_avg > older_avg:
            parts.append(f"近3年平均分（{recent_avg:.1f}）高于前期（{older_avg:.1f}），竞争有加剧趋势。")
        else:
            parts.append(f"近3年平均分（{recent_avg:.1f}）低于或持平前期（{older_avg:.1f}）。")

    return "".join(parts)


def get_score_history(db: Session, school_id: int, major_code: str) -> dict | None:
    """Get historical score lines + trend prediction for a school-major combination."""
    school = db.get(School, school_id)
    if not school:
        return None

    # Query score lines for this school + major_code
    stmt = (
        select(ScoreLine)
        .where(
            ScoreLine.school_id == school_id,
            ScoreLine.major_code == major_code,
        )
        .order_by(ScoreLine.year.desc())
        .limit(5)
    )
    rows = db.execute(stmt).scalars().all()

    if not rows:
        # Try fuzzy: match major_code prefix (discipline level)
        disc_code = major_code[:2] if len(major_code) >= 2 else major_code
        stmt = (
            select(ScoreLine)
            .where(
                ScoreLine.school_id == school_id,
                ScoreLine.major_code.like(f"{disc_code}%"),
            )
            .order_by(ScoreLine.year.desc())
            .limit(5)
        )
        rows = db.execute(stmt).scalars().all()

    if not rows:
        return {
            "school_id": school_id,
            "school_name": school.name,
            "school_level": school.level.value if school.level else "",
            "school_province": school.province,
            "major_code": major_code,
            "major_name": "",
            "score_lines": [],
            "trend_analysis": "该院校专业暂无历史分数线数据",
            "prediction": None,
        }

    # Find major name
    major_name = ""
    sm_row = (
        db.query(Major.name)
        .join(SchoolMajor, SchoolMajor.major_id == Major.id)
        .filter(
            SchoolMajor.school_id == school_id,
            Major.code == major_code,
        )
        .first()
    )
    if sm_row:
        major_name = sm_row[0]
    else:
        # Try prefix match
        sm_row = (
            db.query(Major.name)
            .join(SchoolMajor, SchoolMajor.major_id == Major.id)
            .filter(
                SchoolMajor.school_id == school_id,
                Major.code.like(f"{major_code}%"),
            )
            .first()
        )
        if sm_row:
            major_name = sm_row[0]
        else:
            m = db.query(Major).filter(Major.code == major_code).first()
            if m:
                major_name = m.name

    # Serialize score lines to dicts
    serialized = []
    for sl in sorted(rows, key=lambda r: r.year):
        serialized.append({
            "id": sl.id,
            "year": sl.year,
            "category": sl.category,
            "total_score": sl.total_score,
            "politics_score": sl.politics_score,
            "english_score": sl.english_score,
            "business_score_1": sl.business_score_1,
            "business_score_2": sl.business_score_2,
            "applicant_count": sl.applicant_count,
            "admit_count": sl.admit_count,
            "is_national_line": sl.is_national_line,
            "re_exam_total_score": sl.re_exam_total_score,
            "re_exam_politics_score": sl.re_exam_politics_score,
            "re_exam_english_score": sl.re_exam_english_score,
            "re_exam_business_score_1": sl.re_exam_business_score_1,
            "re_exam_business_score_2": sl.re_exam_business_score_2,
        })

    trend_text = _analyze_trend(rows)
    prediction = _predict_next_year(rows)

    return {
        "school_id": school_id,
        "school_name": school.name,
        "school_level": school.level.value if school.level else "",
        "school_province": school.province,
        "major_code": major_code,
        "major_name": major_name,
        "score_lines": serialized,
        "trend_analysis": trend_text,
        "prediction": prediction,
    }


def _predict_next_year(data_points: list) -> dict | None:
    """Predict next year's score line using weighted linear regression.

    Weights decay exponentially: more recent years matter more.
    """
    scored = [
        (sl.year, sl.total_score)
        for sl in data_points
        if hasattr(sl, 'total_score') and sl.total_score
    ]
    scored.sort(key=lambda x: x[0])

    if len(scored) < 2:
        return None

    years = [s[0] for s in scored]
    scores = [s[1] for s in scored]

    max_year = max(years)
    # Weight: exponential decay with half-life ~2 years
    weights = [pow(0.7, max_year - y) for y in years]

    n = len(years)
    w_sum = sum(weights)
    wx = sum(w * y for w, y in zip(weights, years))
    wy = sum(w * s for w, s in zip(weights, scores))
    wx2 = sum(w * y * y for w, y in zip(weights, years))
    wxy = sum(w * y * s for w, y, s in zip(weights, years, scores))

    denominator = w_sum * wx2 - wx * wx
    if abs(denominator) < 1e-9:
        return None

    slope = (w_sum * wxy - wx * wy) / denominator
    intercept = (wy * wx2 - wx * wxy) / denominator

    next_year = max_year + 1
    predicted = round(intercept + slope * next_year)

    # Compute confidence range based on residuals
    residuals = [
        abs(s - (intercept + slope * y))
        for y, s in zip(years, scores)
    ]
    avg_residual = sum(residuals) / len(residuals)
    confidence_range = round(avg_residual * 1.5)

    # Direction
    recent_years = sorted([s[0] for s in scored])[-3:]
    recent_scores = [s[1] for s in scored if s[0] in recent_years]
    direction = "上升" if slope > 0.5 else "下降" if slope < -0.5 else "稳定"

    return {
        "year": next_year,
        "predicted_score": predicted,
        "confidence_low": max(0, predicted - confidence_range),
        "confidence_high": predicted + confidence_range,
        "direction": direction,
        "annual_change": round(slope, 1),
        "confidence_range": confidence_range,
    }
