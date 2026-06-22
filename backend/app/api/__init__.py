from fastapi import APIRouter

from app.api import schools, majors, score_lines, decisions, profiles, score_cards, needs_analysis

router = APIRouter()
router.include_router(schools.router, prefix="/schools", tags=["schools"])
router.include_router(majors.router, prefix="/majors", tags=["majors"])
router.include_router(score_lines.router, prefix="/score-lines", tags=["score-lines"])
router.include_router(decisions.router, prefix="/decisions", tags=["decisions"])
router.include_router(profiles.router, prefix="/profiles", tags=["profiles"])
router.include_router(score_cards.router, prefix="/score-cards", tags=["score-cards"])
router.include_router(needs_analysis.router, prefix="/needs-analysis", tags=["needs-analysis"])
