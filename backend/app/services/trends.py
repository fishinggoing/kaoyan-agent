"""
Trend analysis utilities for score line data.

Extracted from decision_service.py to keep files under the 800-line limit.
"""

from collections import defaultdict

from sqlalchemy.orm import Session

from app.models import School, Major, SchoolMajor

# Priority ordering: lower value = higher prestige
LEVEL_PRIORITY: dict[str, int] = {
    "C9": 0, "985": 1, "211": 2, "军事院校": 2, "中外合作": 2, "双一流": 3, "普本": 4,
}


def build_trends_bulk(
    db: Session, score_lines: list, schools: list[School]
) -> list[dict]:
    """Aggregate score_lines into per-(school, major) trend summaries.

    Each trend dict provides the keys consumed by compute_recommendations:
    school_name, major_name, major_code, re_exam_avg_score, recent_avg_score.
    """
    if not score_lines:
        return []

    # Group score_lines by (school_id, major_code)
    groups: dict[tuple[int, str], list] = defaultdict(list)
    school_ids: set[int] = set()
    major_codes: set[str] = set()
    for sl in score_lines:
        key = (sl.school_id, sl.major_code)
        groups[key].append(sl)
        school_ids.add(sl.school_id)
        major_codes.add(sl.major_code)

    # Pre-load school name lookup
    school_by_id: dict[int, str] = {s.id: s.name for s in schools}
    for sid in school_ids:
        if sid not in school_by_id:
            s = db.get(School, sid)
            if s:
                school_by_id[sid] = s.name

    # Pre-load major name lookup via SchoolMajor + Major join
    major_name_by_code: dict[str, str] = {}
    if major_codes:
        # First try Major table by code
        majors = db.query(Major).filter(Major.code.in_(major_codes)).all()
        for m in majors:
            major_name_by_code[m.code] = m.name

    # Also try SchoolMajor for (school_id, major_code) pairs
    sm_name_cache: dict[tuple[int, str], str] = {}
    sm_rows = (
        db.query(SchoolMajor.school_id, SchoolMajor.major_id, Major.code, Major.name)
        .join(Major, SchoolMajor.major_id == Major.id)
        .filter(
            SchoolMajor.school_id.in_(school_ids),
            Major.code.in_(major_codes),
        )
        .all()
    )
    for sm_sid, _sm_mid, m_code, m_name in sm_rows:
        sm_name_cache[(sm_sid, m_code)] = m_name
        if m_code not in major_name_by_code:
            major_name_by_code[m_code] = m_name

    trends: list[dict] = []
    for (school_id, major_code), lines in groups.items():
        sname = school_by_id.get(school_id)
        if not sname:
            continue

        # Prefer SchoolMajor->Major name, then Major name, then fallback to code
        mname = sm_name_cache.get(
            (school_id, major_code),
            major_name_by_code.get(major_code, major_code),
        )

        total_scores = [sl.total_score for sl in lines if sl.total_score]
        re_exam_scores = [sl.re_exam_total_score for sl in lines if sl.re_exam_total_score]

        re_exam_avg = sum(re_exam_scores) / len(re_exam_scores) if re_exam_scores else 0
        recent_avg = sum(total_scores) / len(total_scores) if total_scores else 0

        trends.append({
            "school_name": sname,
            "major_name": mname,
            "major_code": major_code,
            "re_exam_avg_score": round(re_exam_avg, 1),
            "recent_avg_score": round(recent_avg, 1),
        })

    return trends
