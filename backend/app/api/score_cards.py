"""Score cards CRUD API — save and compare score lines."""

import json

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.dependencies import get_client_id
from app.models import ScoreCard
from app.api.schemas import ScoreCardCreate
from sqlalchemy import func

router = APIRouter()


@router.get("/")
async def list_cards(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    client_id: str = Depends(get_client_id),
):
    base = select(ScoreCard).where(ScoreCard.client_id == client_id)
    total = db.execute(select(func.count()).select_from(base.subquery())).scalar() or 0
    cards = list(
        db.execute(
            base.order_by(ScoreCard.created_at.desc())
            .offset((page - 1) * size)
            .limit(size)
        ).scalars().all()
    )
    return {
        "success": True,
        "data": {
            "items": [_serialize_card(c) for c in cards],
            "total": total,
            "page": page,
            "size": size,
        },
        "error": None,
    }


@router.post("/")
async def create_card(
    data: ScoreCardCreate,
    db: Session = Depends(get_db),
    client_id: str = Depends(get_client_id),
):
    card = ScoreCard(
        client_id=client_id,
        school_name=data.school_name,
        major_name=data.major_name,
        major_code=data.major_code,
        exam_subjects=json.dumps(data.exam_subjects, ensure_ascii=False),
        score_data_json=json.dumps(data.score_data, ensure_ascii=False),
    )
    db.add(card)
    db.commit()
    db.refresh(card)
    return {"success": True, "data": _serialize_card(card), "error": None}


@router.delete("/{card_id}")
async def delete_card(
    card_id: int,
    db: Session = Depends(get_db),
    client_id: str = Depends(get_client_id),
):
    card = db.get(ScoreCard, card_id)
    if not card or card.client_id != client_id:
        return {"success": False, "data": None, "error": "卡片不存在"}
    db.delete(card)
    db.commit()
    return {"success": True, "data": None, "error": None}


def _serialize_card(c: ScoreCard) -> dict:
    exam_subjects = []
    if c.exam_subjects:
        try:
            exam_subjects = json.loads(c.exam_subjects)
        except (json.JSONDecodeError, TypeError):
            pass

    score_data = []
    if c.score_data_json:
        try:
            score_data = json.loads(c.score_data_json)
        except (json.JSONDecodeError, TypeError):
            pass

    return {
        "id": c.id,
        "school_name": c.school_name,
        "major_name": c.major_name,
        "major_code": c.major_code,
        "exam_subjects": exam_subjects,
        "score_data": score_data,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }
