from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.dependencies import get_client_id
from app.services import profile_service as svc
from app.api.schemas import ProfileCreate, ProfileUpdate

router = APIRouter()


@router.get("/")
async def list_profiles(
    db: Session = Depends(get_db),
    client_id: str = Depends(get_client_id),
):
    profiles = svc.list_profiles(db, client_id)
    return {
        "success": True,
        "data": {
            "items": [_serialize_profile(p) for p in profiles],
            "total": len(profiles),
        },
        "error": None,
    }


@router.post("/")
async def create_profile(
    data: ProfileCreate,
    db: Session = Depends(get_db),
    client_id: str = Depends(get_client_id),
):
    profile = svc.create_profile(db, data.model_dump(exclude_none=True), client_id)
    return {
        "success": True,
        "data": _serialize_profile(profile),
        "error": None,
    }


@router.get("/{profile_id}")
async def get_profile(
    profile_id: int,
    db: Session = Depends(get_db),
    client_id: str = Depends(get_client_id),
):
    profile = svc.get_profile(db, profile_id, client_id)
    return {
        "success": True,
        "data": _serialize_profile(profile),
        "error": None,
    }


@router.put("/{profile_id}")
async def update_profile(
    profile_id: int,
    data: ProfileUpdate,
    db: Session = Depends(get_db),
    client_id: str = Depends(get_client_id),
):
    profile = svc.update_profile(db, profile_id, data.model_dump(exclude_none=True), client_id)
    return {
        "success": True,
        "data": _serialize_profile(profile),
        "error": None,
    }


@router.delete("/{profile_id}")
async def delete_profile(
    profile_id: int,
    db: Session = Depends(get_db),
    client_id: str = Depends(get_client_id),
):
    svc.delete_profile(db, profile_id, client_id)
    return {"success": True, "data": None, "error": None}


def _serialize_profile(p) -> dict:
    import json as _json

    exam_config = {}
    if p.exam_config:
        try:
            exam_config = _json.loads(p.exam_config)
        except (ValueError, TypeError):
            pass

    strengths = {}
    if p.subject_strengths:
        try:
            strengths = _json.loads(p.subject_strengths)
        except (ValueError, TypeError):
            pass

    pref_weights = None
    if p.preference_weights:
        try:
            pref_weights = _json.loads(p.preference_weights)
        except (ValueError, TypeError):
            pass

    return {
        "id": p.id,
        "nickname": p.nickname,
        "undergraduate_school": p.undergraduate_school,
        "undergraduate_major": p.undergraduate_major,
        "target_province": p.target_province,
        "target_level": p.target_level,
        "estimated_score": p.estimated_score,
        "available_hours_per_day": p.available_hours_per_day,
        "exam_year": p.exam_year,
        "notes": p.notes,
        "exam_config": exam_config,
        "subject_strengths": strengths,
        "preference_weights": pref_weights,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }
