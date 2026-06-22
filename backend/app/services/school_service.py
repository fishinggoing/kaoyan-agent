from sqlalchemy import select, func, or_, case
from sqlalchemy.orm import Session

from app.models import School, SchoolLevel, SchoolCategory
from app.utils.exceptions import NotFoundError

# Treat NULL category as GRAD_EXAM (backward-compatible with pre-migration data)
_GRAD_EXAM_FILTER = or_(
    School.category == SchoolCategory.GRAD_EXAM,
    School.category.is_(None),
)

# Only include schools with known type (excludes empty-shell imports)
_HAS_TYPE = School.school_type.isnot(None)


def _get_level_in(db: Session, level_value: str) -> list[str]:
    """Map a front-end level filter value to the set of DB level values to include.

    Levels are inclusive: selecting "985" includes C9, selecting "211"
    includes C9 + 985, etc.  This way the filter shows all schools at or
    above the selected tier.
    """
    _inclusive = {
        "C9":       ["C9"],
        "985":      ["C9", "NINE_EIGHT_FIVE"],
        "211":      ["C9", "NINE_EIGHT_FIVE", "TWO_ONE_ONE"],
        "双一流":   ["C9", "NINE_EIGHT_FIVE", "TWO_ONE_ONE", "DOUBLE_FIRST_CLASS"],
        "普本":     ["REGULAR"],
    }
    return _inclusive.get(level_value, [level_value])


def get_filter_options(db: Session) -> dict:
    """Return available filter options with counts for the guided selection UI.

    Only 考研高校 are counted. Level counts are inclusive (e.g. "985"
    count includes C9 schools), matching the inclusive filter behavior in
    list_schools().
    """
    prov_stmt = (
        select(School.province, func.count(School.id))
        .where(_GRAD_EXAM_FILTER, _HAS_TYPE)
        .group_by(School.province)
        .order_by(School.province)
    )
    provinces = [{"province": p, "count": c} for p, c in db.execute(prov_stmt).all()]

    # Level counts — only 考研高校, with inclusive tier logic
    base = (
        select(School.level, func.count(School.id))
        .where(_GRAD_EXAM_FILTER, _HAS_TYPE)
        .group_by(School.level)
    )
    raw: dict[str, int] = {lv.name if hasattr(lv, 'name') else lv: c for lv, c in db.execute(base).all()}

    level_counts: dict[str, int] = {}
    for label, included in [("C9", ["C9"]),
                             ("985", ["C9", "NINE_EIGHT_FIVE"]),
                             ("211", ["C9", "NINE_EIGHT_FIVE", "TWO_ONE_ONE"]),
                             ("双一流", ["C9", "NINE_EIGHT_FIVE", "TWO_ONE_ONE", "DOUBLE_FIRST_CLASS"]),
                             ("普本", ["REGULAR"])]:
        total = sum(raw.get(lv, 0) for lv in included)
        if total > 0:
            level_counts[label] = total

    return {
        "provinces": provinces,
        "levels": level_counts,
    }


def get_school_options(
    db: Session,
    province: str | None = None,
    level: str | None = None,
    keyword: str | None = None,
    limit: int = 100,
) -> list[dict]:
    """Return lightweight school options for cascade selectors.

    Filters out sub-units (graduate schools, research institutes) and shows
    only standalone higher-education institutions.
    """
    # Exclude sub-units: graduate-school-only entries, research institutes, party schools
    EXCLUDE_PATTERNS = [
        "%研究生院%", "%研究院%", "%研究所%", "%研究中心%",
        "%党校%", "%行政学院%", "%进修学院%", "%培训中心%",
        "%教育基地%", "%科研中心%",
    ]

    stmt = select(
        School.id, School.name, School.province, School.city,
        School.level, School.category, School.school_type, School.ranking_national,
    )

    if province:
        stmt = stmt.where(School.province == province)
    if level:
        stmt = stmt.where(School.level.in_(_get_level_in(db, level)))
    if keyword:
        stmt = stmt.where(School.name.ilike(f"%{keyword}%"))

    for pat in EXCLUDE_PATTERNS:
        stmt = stmt.where(School.name.notlike(pat))

    stmt = stmt.where(_HAS_TYPE)

    stmt = stmt.order_by(
        School.ranking_national.asc().nulls_last(),
        School.name.asc(),
    ).limit(limit)

    rows = db.execute(stmt).all()
    return [
        {
            "id": r.id,
            "name": r.name,
            "province": r.province,
            "city": r.city,
            "level": r.level.value if r.level else None,
            "category": r.category.value if r.category else None,
            "school_type": r.school_type.value if r.school_type else None,
            "ranking_national": r.ranking_national,
        }
        for r in rows
    ]


def list_schools(
    db: Session,
    name: str | None = None,
    province: str | None = None,
    level: str | None = None,
    school_type: str | None = None,
    page: int = 1,
    size: int = 20,
) -> tuple[list[School], int]:
    stmt = select(School).where(_GRAD_EXAM_FILTER, _HAS_TYPE)

    if name:
        stmt = stmt.where(or_(
            School.name.ilike(f"%{name}%"),
            School.description.ilike(f"%{name}%"),
        ))
    if province:
        stmt = stmt.where(School.province == province)
    if level:
        stmt = stmt.where(School.level.in_(_get_level_in(db, level)))
    if school_type:
        stmt = stmt.where(School.school_type == school_type)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = db.execute(count_stmt).scalar() or 0

    stmt = stmt.offset((page - 1) * size).limit(size).order_by(School.ranking_national.asc().nulls_last())
    items = db.execute(stmt).scalars().all()

    return list(items), total


def search_schools(
    db: Session,
    query: str,
    page: int = 1,
    size: int = 20,
) -> tuple[list[dict], int]:
    """Multi-field relevance search across school name, description, province, and city.

    Uses weighted LIKE matching to rank results. Falls back to listing top schools
    by ranking when query is empty.
    """
    if not query or not query.strip():
        stmt = select(School).where(_GRAD_EXAM_FILTER, _HAS_TYPE).order_by(School.ranking_national.asc().nulls_last())
        count_stmt = select(func.count()).select_from(School).where(_GRAD_EXAM_FILTER, _HAS_TYPE)
        total = db.execute(count_stmt).scalar() or 0
        stmt = stmt.offset((page - 1) * size).limit(size)
        items = db.execute(stmt).scalars().all()
        return [_school_to_dict(s) for s in items], total

    q = f"%{query.strip()}%"
    relevance = (
        case(
            (School.name.ilike(q), 4),
            (School.description.ilike(q), 2),
            (School.province.ilike(q), 1),
            (School.city.ilike(q), 1),
            else_=0,
        )
    )

    search_filter = or_(
        School.name.ilike(q),
        School.description.ilike(q),
        School.province.ilike(q),
        School.city.ilike(q),
    )

    stmt = (
        select(School, relevance.label("relevance"))
        .where(search_filter, _GRAD_EXAM_FILTER, _HAS_TYPE)
        .order_by(relevance.desc(), School.ranking_national.asc().nulls_last())
    )

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = db.execute(count_stmt).scalar() or 0

    stmt = stmt.offset((page - 1) * size).limit(size)
    rows = db.execute(stmt).all()

    results = []
    for school, rel in rows:
        d = _school_to_dict(school)
        d["relevance"] = rel
        results.append(d)

    return results, total


def _school_to_dict(s: School) -> dict:
    return {
        "id": s.id,
        "name": s.name,
        "province": s.province,
        "city": s.city,
        "level": s.level.value if s.level else None,
        "category": s.category.value if s.category else None,
        "school_type": s.school_type.value if s.school_type else None,
        "is_graduate_school": s.is_graduate_school,
        "website": s.website,
        "description": s.description,
        "ranking_national": s.ranking_national,
        "graduate_school_url": s.graduate_school_url,
    }


def get_schools_by_ids(db: Session, ids: list[int]) -> list[dict]:
    schools = list(db.execute(select(School).where(School.id.in_(ids))).scalars().all())
    return [_school_to_dict(s) for s in schools]


def get_school(db: Session, school_id: int) -> School:
    school = db.get(School, school_id)
    if not school:
        raise NotFoundError(f"School {school_id} not found")
    return school


def create_school(db: Session, data: dict) -> School:
    school = School(**data)
    db.add(school)
    db.commit()
    db.refresh(school)
    return school


def update_school(db: Session, school_id: int, data: dict) -> School:
    school = get_school(db, school_id)
    for key, value in data.items():
        if hasattr(school, key):
            setattr(school, key, value)
    db.commit()
    db.refresh(school)
    return school


def delete_school(db: Session, school_id: int) -> None:
    school = get_school(db, school_id)
    db.delete(school)
    db.commit()
