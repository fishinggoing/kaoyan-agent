from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.services.score_service import (
    list_school_majors,
    get_school_major_detail,
    get_school_enrollment_summary,
    get_score_history,
)

router = APIRouter()


@router.get("/")
async def list_enrollment(
    school_id: int | None = Query(None, description="院校ID"),
    year: int | None = Query(None, description="年份"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """List school majors with enrollment data."""
    items, total = list_school_majors(db, school_id=school_id, year=year, page=page, size=size)
    return {
        "success": True,
        "data": {"items": items, "total": total, "page": page, "size": size},
        "error": None,
    }


@router.get("/{school_major_id}")
async def get_enrollment_detail(
    school_major_id: int,
    db: Session = Depends(get_db),
):
    """Get single school-major enrollment detail."""
    data = get_school_major_detail(db, school_major_id)
    if not data:
        return {"success": False, "data": None, "error": "Not found"}
    return {"success": True, "data": data, "error": None}


@router.get("/school/{school_id}/summary")
async def get_enrollment_summary(
    school_id: int,
    db: Session = Depends(get_db),
):
    """Get aggregated enrollment summary for a school."""
    data = get_school_enrollment_summary(db, school_id)
    return {"success": True, "data": data, "error": None}


@router.get("/school/{school_id}/major/{major_code}/history")
async def get_score_history_endpoint(
    school_id: int,
    major_code: str,
    db: Session = Depends(get_db),
):
    """Get historical score lines + trend prediction for a school-major combination."""
    data = get_score_history(db, school_id, major_code)
    if data is None:
        return {"success": False, "data": None, "error": "School not found or no score data available"}
    return {"success": True, "data": data, "error": None}
