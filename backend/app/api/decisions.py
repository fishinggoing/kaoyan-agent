from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.services import decision_service as svc
from app.api.schemas import AnalyzeRequest, DecisionRequest, DecisionFromChatRequest
from app.utils.input_filter import sanitize_for_llm

router = APIRouter()


@router.post("/analyze")
async def analyze_school_major(data: AnalyzeRequest, db: Session = Depends(get_db)):
    """针对特定院校+专业的 AI 分析"""
    result = await svc.analyze_school_major(
        db=db,
        school_id=data.school_id,
        major_code=data.major_code,
        estimated_score=data.estimated_score,
    )

    return {
        "success": True,
        "data": {
            "risk_level": result.risk_level,
            "match_score": result.match_score,
            "score_trend": result.score_trend,
            "competition": result.competition,
            "pros": result.pros,
            "cons": result.cons,
            "analysis": result.analysis,
            "preparation_tips": result.preparation_tips,
        },
        "error": None,
    }


@router.post("/recommend")
async def recommend_schools(data: DecisionRequest, db: Session = Depends(get_db)):
    result, name_to_subjects = await svc.recommend(
        db=db,
        profile_id=data.profile_id,
        target_province=data.target_province,
        target_level=data.target_level,
        target_major_keyword=sanitize_for_llm(data.major_keyword) if data.major_keyword else None,
    )

    return {
        "success": True,
        "data": {
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
                    "exam_subjects": name_to_subjects.get((r.school_name, r.major_code), []),
                    "major_strength_score": r.major_strength_score,
                    "major_strength_label": r.major_strength_label,
                }
                for r in result.recommendations
            ],
            "analysis": result.analysis,
            "plan_suggestion": result.plan_suggestion,
        },
        "error": None,
    }


@router.post("/from-chat")
async def recommend_from_chat(data: DecisionFromChatRequest, db: Session = Depends(get_db)):
    """Fast recommendation from school names extracted in NeedsChat conversation."""
    profile_id = data.profile_id
    school_names = data.school_names

    result, name_to_subjects = await svc.recommend_by_school_names(
        db=db,
        profile_id=profile_id,
        school_names=[sanitize_for_llm(str(n)) for n in school_names],
        target_province=data.target_province,
        target_level=data.target_level,
        target_major_keyword=sanitize_for_llm(data.major_keyword) if data.major_keyword else None,
    )

    return {
        "success": True,
        "data": {
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
                    "exam_subjects": name_to_subjects.get((r.school_name, r.major_code), []),
                    "major_strength_score": r.major_strength_score,
                    "major_strength_label": r.major_strength_label,
                }
                for r in result.recommendations
            ],
            "analysis": result.analysis,
            "plan_suggestion": result.plan_suggestion,
        },
        "error": None,
    }
