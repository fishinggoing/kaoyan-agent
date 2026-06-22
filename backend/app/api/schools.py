import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models import College

logger = logging.getLogger(__name__)
from app.services.school_service import (
    list_schools, search_schools, get_school, create_school, update_school, delete_school,
    get_filter_options, get_school_options,
)
from app.api.schemas import SchoolCreate, SchoolUpdate

router = APIRouter()


@router.get("/filters")
async def get_filters_endpoint(db: Session = Depends(get_db)):
    """Return available filter options for guided selection UI."""
    options = get_filter_options(db)
    return {"success": True, "data": options, "error": None}


@router.get("/options")
async def school_options_endpoint(
    province: str | None = Query(None),
    level: str | None = Query(None),
    keyword: str | None = Query(None),
    limit: int = Query(100, ge=10, le=500),
    db: Session = Depends(get_db),
):
    """Return lightweight school list for cascade selectors."""
    options = get_school_options(db, province, level, keyword, limit)
    return {"success": True, "data": {"items": options, "total": len(options)}, "error": None}


@router.get("/search")
async def search_schools_endpoint(
    q: str = Query(..., description="搜索关键词"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=500),
    db: Session = Depends(get_db),
):
    items, total = search_schools(db, q, page, size)
    return {
        "success": True,
        "data": {"items": items, "total": total, "page": page, "size": size},
        "error": None,
    }


@router.get("/vector-search")
async def vector_search_endpoint(
    q: str = Query(..., description="语义搜索关键词"),
    top_k: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """Semantic vector search over schools via ChromaDB, with SQL fallback."""
    from app.db.vector_store import search_schools_vector
    from app.services.school_service import get_schools_by_ids

    try:
        results = search_schools_vector(q, top_k)
        if results:
            school_ids = [int(r["school_id"]) for r in results if r.get("school_id")]
            schools = get_schools_by_ids(db, school_ids) if school_ids else []
            id_to_school = {s["id"]: s for s in schools}
            items = [
                {**id_to_school.get(r["school_id"], {}), "vector_relevance": r.get("relevance", 0)}
                for r in results
                if r.get("school_id") in id_to_school
            ]
            return {
                "success": True,
                "data": {"items": items, "total": len(items), "method": "vector"},
                "error": None,
            }
    except Exception:
        logger.warning("Vector search failed, falling back to SQL", exc_info=True)

    # Fallback to SQL
    items, total = search_schools(db, q, 1, top_k)
    return {
        "success": True,
        "data": {"items": items, "total": total, "method": "sql_fallback"},
        "error": None,
    }


@router.get("/")
async def list_schools_endpoint(
    name: str | None = Query(None, description="院校名称模糊搜索"),
    province: str | None = Query(None, description="省份"),
    level: str | None = Query(None, description="院校层次 (C9/985/211/双一流/普本)"),
    school_type: str | None = Query(None, description="院校类型"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=500),
    db: Session = Depends(get_db),
):
    items, total = list_schools(db, name, province, level, school_type, page, size)
    return {
        "success": True,
        "data": {"items": items, "total": total, "page": page, "size": size},
        "error": None,
    }


@router.get("/{school_id}/colleges")
async def get_school_colleges(school_id: int, db: Session = Depends(get_db)):
    """Return the list of colleges (学院) for a given school."""
    from sqlalchemy import select
    colleges = list(
        db.execute(
            select(College).where(College.school_id == school_id).order_by(College.name)
        ).scalars().all()
    )
    return {
        "success": True,
        "data": [
            {
                "id": c.id,
                "name": c.name,
                "description": c.description,
            }
            for c in colleges
        ],
        "error": None,
    }


@router.get("/{school_id}")
async def get_school_endpoint(school_id: int, db: Session = Depends(get_db)):
    school = get_school(db, school_id)
    return {"success": True, "data": school, "error": None}


@router.post("/")
async def create_school_endpoint(data: SchoolCreate, db: Session = Depends(get_db)):
    school = create_school(db, data.model_dump())
    return {"success": True, "data": school, "error": None}


@router.put("/{school_id}")
async def update_school_endpoint(school_id: int, data: SchoolUpdate, db: Session = Depends(get_db)):
    school = update_school(db, school_id, data.model_dump(exclude_none=True))
    return {"success": True, "data": school, "error": None}


@router.delete("/{school_id}")
async def delete_school_endpoint(school_id: int, db: Session = Depends(get_db)):
    delete_school(db, school_id)
    return {"success": True, "data": None, "error": None}
