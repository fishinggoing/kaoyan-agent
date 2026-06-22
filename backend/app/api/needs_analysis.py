"""Needs analysis chat API — conversational user needs assessment."""

import json
import logging

from fastapi import APIRouter, Depends
from sqlalchemy import select, delete
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.dependencies import get_client_id
from app.models import UserProfile, RecommendationCache
from app.agents.needs_analysis import needs_analysis_agent, NeedsAnalysisResult
from app.api.schemas import NeedsChatRequest, NeedsFinalizeRequest, SaveWeightsRequest
from app.services import decision_service as decision_svc
from app.utils.input_filter import validate_chat_input, sanitize_for_llm

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_profile(db: Session, profile_id: int, client_id: str) -> UserProfile | None:
    profile = db.get(UserProfile, profile_id)
    if not profile or profile.client_id != client_id:
        return None
    return profile


def _profile_to_chat_context(profile: UserProfile) -> dict:
    """Extract relevant profile fields for the needs-analysis agent."""
    exam_config = {}
    if profile.exam_config:
        try:
            exam_config = json.loads(profile.exam_config)
        except (json.JSONDecodeError, TypeError):
            pass

    strengths = {}
    if profile.subject_strengths:
        try:
            strengths = json.loads(profile.subject_strengths)
        except (json.JSONDecodeError, TypeError):
            pass

    return {
        "undergraduate_school": profile.undergraduate_school,
        "undergraduate_major": profile.undergraduate_major,
        "target_province": profile.target_province,
        "target_level": profile.target_level,
        "estimated_score": profile.estimated_score,
        "exam_year": profile.exam_year,
        "exam_config": {
            "math": exam_config.get("math") if exam_config else None,
            "english": exam_config.get("english") if exam_config else None,
        },
        "subject_strengths": strengths or {},
    }


def _serialize_recommendations(result, name_to_subjects: dict) -> list[dict]:
    """Convert DecisionResult + exam_subjects map to JSON-serializable list."""
    return [
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
            "exam_subjects": name_to_subjects.get((r.school_name, r.major_code), []),
        }
        for r in result.recommendations
    ]


async def _maybe_generate_recommendations(
    db: Session, profile_id: int, result: NeedsAnalysisResult,
) -> dict | None:
    """Fallback: if regex detected school names + recommend intent, generate preview cards."""
    rp = (result.intent_params or {}).get("recommend", {})
    school_names = rp.get("schools_mentioned", [])
    if not school_names or "recommend" not in (result.intents or []):
        return None

    try:
        decision_result, name_to_subjects = await decision_svc.recommend_by_school_names(
            db=db,
            profile_id=profile_id,
            school_names=school_names,
            target_province=rp.get("target_province"),
            target_level=rp.get("target_level"),
            target_major_keyword=rp.get("major_keyword"),
        )
        recs = _serialize_recommendations(decision_result, name_to_subjects)
        if not recs:
            return None
        return {
            "recommendations": recs,
            "analysis": decision_result.analysis,
            "source_schools": school_names,
        }
    except Exception:
        logger.warning("Failed to generate recommendation preview", exc_info=True)
        return None


def _get_school_cards(
    db: Session, result: NeedsAnalysisResult,
) -> list[dict] | None:
    """Get school info cards from marker-extracted [[SCHOOLS]] names.

    This is the primary mechanism — the LLM explicitly marks school names.
    No keyword trigger or profile scoring needed.
    """
    if not result.school_names:
        return None
    try:
        return decision_svc.get_school_info_by_names(db, result.school_names)
    except Exception:
        logger.warning("Failed to get school cards", exc_info=True)
        return None


@router.post("/chat")
async def chat(
    data: NeedsChatRequest,
    db: Session = Depends(get_db),
    client_id: str = Depends(get_client_id),
):
    """Send a message in the needs analysis conversation."""
    profile = _get_profile(db, data.profile_id, client_id)
    if not profile:
        return {"success": False, "data": None, "error": "Profile not found"}

    err = validate_chat_input(data.message, data.history)
    if err:
        return {"success": False, "data": None, "error": err}

    result = await needs_analysis_agent.chat(
        data.history,
        sanitize_for_llm(data.message),
        profile=_profile_to_chat_context(profile),
    )

    # Auto-save weights if extraction was successful
    if result.weights:
        profile.preference_weights = json.dumps(result.weights, ensure_ascii=False)
        db.execute(
            delete(RecommendationCache).where(RecommendationCache.profile_id == data.profile_id)
        )
        db.commit()

    # Agent-to-agent: if school names detected via [[SCHOOLS]] markers, get cards
    school_cards = _get_school_cards(db, result)
    # Fallback: regex-based recommendation preview
    preview = await _maybe_generate_recommendations(db, data.profile_id, result) if not school_cards else None

    return {
        "success": True,
        "data": {
            "reply": result.reply,
            "weights": result.weights,
            "is_complete": result.is_complete,
            "intents": result.intents,
            "intent_params": result.intent_params,
            "recommendation_preview": preview,
            "school_cards": school_cards,
        },
        "error": None,
    }


@router.post("/finalize")
async def finalize(
    data: NeedsFinalizeRequest,
    db: Session = Depends(get_db),
    client_id: str = Depends(get_client_id),
):
    """Force extraction of preference weights from conversation history."""
    profile = _get_profile(db, data.profile_id, client_id)
    if not profile:
        return {"success": False, "data": None, "error": "Profile not found"}

    err = validate_chat_input("finalize", data.history)
    if err:
        return {"success": False, "data": None, "error": err}

    result = await needs_analysis_agent.finalize(data.history)

    if result.weights:
        profile.preference_weights = json.dumps(result.weights, ensure_ascii=False)
        db.execute(
            delete(RecommendationCache).where(RecommendationCache.profile_id == data.profile_id)
        )
        db.commit()

    # Agent-to-agent: if school names detected via [[SCHOOLS]] markers, get cards
    school_cards = _get_school_cards(db, result)
    # Fallback: regex-based recommendation preview
    preview = await _maybe_generate_recommendations(db, data.profile_id, result) if not school_cards else None

    return {
        "success": True,
        "data": {
            "reply": result.reply,
            "weights": result.weights,
            "is_complete": result.is_complete,
            "intents": result.intents,
            "intent_params": result.intent_params,
            "recommendation_preview": preview,
            "school_cards": school_cards,
        },
        "error": None,
    }


@router.get("/weights/{profile_id}")
async def get_weights(
    profile_id: int,
    db: Session = Depends(get_db),
    client_id: str = Depends(get_client_id),
):
    """Get saved preference weights for a profile."""
    profile = _get_profile(db, profile_id, client_id)
    if not profile:
        return {"success": False, "data": None, "error": "Profile not found"}

    weights = None
    if profile.preference_weights:
        try:
            weights = json.loads(profile.preference_weights)
        except (json.JSONDecodeError, TypeError):
            pass

    return {"success": True, "data": weights, "error": None}


@router.post("/weights/{profile_id}")
async def save_weights(
    profile_id: int,
    data: SaveWeightsRequest,
    db: Session = Depends(get_db),
    client_id: str = Depends(get_client_id),
):
    """Manually save/update preference weights for a profile."""
    profile = _get_profile(db, profile_id, client_id)
    if not profile:
        return {"success": False, "data": None, "error": "Profile not found"}

    weights = data.weights
    if weights:
        profile.preference_weights = json.dumps(weights, ensure_ascii=False)
        db.execute(
            delete(RecommendationCache).where(RecommendationCache.profile_id == profile_id)
        )
        db.commit()

    return {"success": True, "data": weights, "error": None}
