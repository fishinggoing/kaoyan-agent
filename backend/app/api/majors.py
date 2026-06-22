from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models import Major, School, SchoolMajor
from app.utils.exceptions import NotFoundError

router = APIRouter()


@router.get("/")
async def list_majors(
    name: str | None = Query(None, description="专业名称模糊搜索"),
    code: str | None = Query(None, description="专业代码"),
    category: str | None = Query(None, description="学科门类"),
    degree_type: str | None = Query(None, description="学位类型: 学术学位/专业学位"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=500),
    db: Session = Depends(get_db),
):
    stmt = select(Major)
    if name:
        stmt = stmt.where(Major.name.ilike(f"%{name}%"))
    if code:
        stmt = stmt.where(Major.code.like(f"{code}%"))
    if category:
        stmt = stmt.where(Major.category == category)
    if degree_type:
        stmt = stmt.where(Major.degree_type == degree_type)

    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0
    stmt = stmt.offset((page - 1) * size).limit(size).order_by(Major.code)
    items = db.execute(stmt).scalars().all()

    result = []
    for m in items:
        # Count schools offering this major
        school_count = db.execute(
            select(func.count(SchoolMajor.id)).where(SchoolMajor.major_id == m.id)
        ).scalar() or 0

        result.append({
            "id": m.id,
            "code": m.code,
            "name": m.name,
            "category": m.category,
            "discipline": m.discipline,
            "degree_type": m.degree_type,
            "school_count": school_count,
        })

    return {
        "success": True,
        "data": {"items": result, "total": total, "page": page, "size": size},
        "error": None,
    }


@router.get("/categories")
async def list_categories(db: Session = Depends(get_db)):
    stmt = select(Major.category).distinct().where(Major.category.isnot(None)).order_by(Major.category)
    categories = db.execute(stmt).scalars().all()
    return {"success": True, "data": list(categories), "error": None}


@router.get("/{major_id}")
async def get_major(major_id: int, db: Session = Depends(get_db)):
    major = db.get(Major, major_id)
    if not major:
        raise NotFoundError(f"Major {major_id} not found")

    # Get schools offering this major
    school_majors = db.execute(
        select(SchoolMajor, School).join(School).where(SchoolMajor.major_id == major_id)
    ).all()

    schools_data = []
    for sm, school in school_majors:
        schools_data.append({
            "school_id": school.id,
            "school_name": school.name,
            "school_level": school.level.value if school.level else "",
            "school_province": school.province,
            "department": sm.department,
            "direction": sm.direction,
            "study_mode": sm.study_mode,
            "planned_enrollment": sm.planned_enrollment,
            "year": sm.year,
        })

    return {
        "success": True,
        "data": {
            "id": major.id,
            "code": major.code,
            "name": major.name,
            "category": major.category,
            "discipline": major.discipline,
            "degree_type": major.degree_type,
            "schools": schools_data,
        },
        "error": None,
    }


@router.get("/school/{school_id}")
async def list_school_majors(
    school_id: int,
    year: int | None = Query(None, description="年份，默认2026"),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    stmt = select(SchoolMajor).where(SchoolMajor.school_id == school_id)
    if year:
        stmt = stmt.where(SchoolMajor.year == year)

    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0
    stmt = stmt.order_by(
        SchoolMajor.planned_enrollment.desc().nullslast(),
        SchoolMajor.department
    )
    stmt = stmt.offset((page - 1) * size).limit(size)
    items = db.execute(stmt).scalars().all()

    major_ids = {sm.major_id for sm in items}
    majors = {m.id: m for m in db.execute(select(Major).where(Major.id.in_(major_ids))).scalars()}

    result = []
    for sm in items:
        m = majors.get(sm.major_id)
        result.append({
            "id": sm.id,
            "school_id": sm.school_id,
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
            "exam_politics": sm.exam_politics,
            "exam_english": sm.exam_english,
            "exam_math": sm.exam_math,
            "exam_course1_name": sm.exam_course1_name,
            "exam_course1_code": sm.exam_course1_code,
            "exam_course2_name": sm.exam_course2_name,
            "exam_course2_code": sm.exam_course2_code,
            "exam_course3_name": sm.exam_course3_name,
            "exam_course3_code": sm.exam_course3_code,
            "year": sm.year,
        })

    return {
        "success": True,
        "data": {"items": result, "total": total, "page": page, "size": size},
        "error": None,
    }
