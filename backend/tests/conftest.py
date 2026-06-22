import os
import sys
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Set test API key BEFORE any app imports (Pydantic Settings reads env at import time)
os.environ["API_KEY"] = "test-api-key-at-least-16-chars"

from app.db.database import Base, get_db
from app.main import app
from app.models import (
    School, Major, SchoolMajor, ScoreLine, UserProfile,
    SchoolLevel, SchoolType, DegreeLevel,
)

# Delete order matters for FK constraints: children before parents
ALL_TABLES = [ScoreLine, SchoolMajor, Major, UserProfile, School]


# ── Mock DeepSeek client ──

MOCK_JSON_RESPONSE = '{"summary": "test"}'


def _make_mock_openai():
    """Create a mock OpenAI client that returns a canned response."""
    mock_client = MagicMock()
    mock_completion = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = MOCK_JSON_RESPONSE
    mock_completion.choices = [mock_choice]
    mock_client.chat.completions.create.return_value = mock_completion
    return mock_client


@pytest.fixture(autouse=True)
def mock_openai():
    """Mock OpenAI client in all agent modules so no real API calls are made."""
    mock_client = _make_mock_openai()

    targets = [
        "openai.AsyncOpenAI",
        "app.agents.orchestrator.AsyncOpenAI",
        "app.agents.needs_analysis.AsyncOpenAI",
    ]
    patchers = [patch(t, return_value=mock_client) for t in targets]
    for p in patchers:
        p.start()

    yield mock_client

    for p in patchers:
        p.stop()


# ── Test database ──

TEST_DB_URL = "sqlite://"  # In-memory for faster tests

@pytest.fixture(scope="session")
def engine():
    eng = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=eng)
    yield eng
    Base.metadata.drop_all(bind=eng)


@pytest.fixture
def db_session(engine):
    """Per-test DB session with cleanup (children-first to respect FK order)."""
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.rollback()
        for table in ALL_TABLES:
            session.execute(delete(table))
        session.commit()
        session.close()


@pytest.fixture
def client(db_session):
    """Test client with DB dependency override."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as tc:
        yield tc
    app.dependency_overrides.clear()


@pytest.fixture
def test_headers() -> dict[str, str]:
    """Standard headers for test requests (auth + client identity)."""
    return {
        "X-API-Key": "test-api-key-at-least-16-chars",
        "X-Client-ID": "test-client-001",
    }


# ── Sample data fixtures ──

@pytest.fixture
def sample_school(db_session) -> School:
    school = School(
        name="清华大学",
        province="北京",
        city="北京",
        level=SchoolLevel.C9,
        school_type=SchoolType.COMPREHENSIVE,
        is_graduate_school=True,
        website="https://www.tsinghua.edu.cn",
        description="中国顶尖综合性研究型大学",
        ranking_national=1,
    )
    db_session.add(school)
    db_session.commit()
    db_session.refresh(school)
    return school


@pytest.fixture
def sample_schools(db_session) -> list[School]:
    schools = [
        School(name="北京大学", province="北京", city="北京", level=SchoolLevel.C9,
               school_type=SchoolType.COMPREHENSIVE, is_graduate_school=True, ranking_national=2),
        School(name="浙江大学", province="浙江", city="杭州", level=SchoolLevel.C9,
               school_type=SchoolType.COMPREHENSIVE, is_graduate_school=True, ranking_national=3),
        School(name="武汉大学", province="湖北", city="武汉", level=SchoolLevel.NINE_EIGHT_FIVE,
               school_type=SchoolType.COMPREHENSIVE, is_graduate_school=True, ranking_national=10),
        School(name="深圳大学", province="广东", city="深圳", level=SchoolLevel.REGULAR,
               school_type=SchoolType.COMPREHENSIVE, is_graduate_school=False, ranking_national=70),
    ]
    for s in schools:
        db_session.add(s)
    db_session.commit()
    return schools


@pytest.fixture
def sample_major(db_session, sample_school) -> Major:
    major = Major(
        code="081200",
        name="计算机科学与技术",
        category="工学",
        discipline="计算机科学与技术",
        degree_type="学术学位",
    )
    db_session.add(major)
    db_session.commit()
    db_session.refresh(major)
    # Also create a SchoolMajor junction
    sm = SchoolMajor(
        school_id=sample_school.id,
        major_id=major.id,
        department="计算机学院",
        direction="人工智能方向",
        study_mode="全日制",
        planned_enrollment=35,
        year=2026,
    )
    db_session.add(sm)
    db_session.commit()
    return major


@pytest.fixture
def sample_score_lines(db_session, sample_school, sample_major) -> list[ScoreLine]:
    lines = [
        ScoreLine(school_id=sample_school.id, major_code=sample_major.code, year=2021,
                  category="学硕", total_score=350, politics_score=55, english_score=55,
                  business_score_1=85, business_score_2=85, applicant_count=500, admit_count=35),
        ScoreLine(school_id=sample_school.id, major_code=sample_major.code, year=2022,
                  category="学硕", total_score=355, politics_score=55, english_score=55,
                  business_score_1=85, business_score_2=85, applicant_count=550, admit_count=35),
        ScoreLine(school_id=sample_school.id, major_code=sample_major.code, year=2023,
                  category="学硕", total_score=360, politics_score=60, english_score=60,
                  business_score_1=90, business_score_2=90, applicant_count=600, admit_count=35),
        ScoreLine(school_id=sample_school.id, major_code=sample_major.code, year=2024,
                  category="学硕", total_score=358, politics_score=55, english_score=55,
                  business_score_1=90, business_score_2=90, applicant_count=620, admit_count=38),
        ScoreLine(school_id=sample_school.id, major_code=sample_major.code, year=2025,
                  category="学硕", total_score=365, politics_score=60, english_score=60,
                  business_score_1=90, business_score_2=90, applicant_count=650, admit_count=40),
    ]
    for line in lines:
        db_session.add(line)
    db_session.commit()
    return lines


@pytest.fixture
def sample_profile(db_session) -> UserProfile:
    profile = UserProfile(
        client_id="test-client-001",
        nickname="测试考生",
        undergraduate_school="武汉理工大学",
        undergraduate_major="软件工程",
        target_province="北京",
        target_level="985",
        estimated_score=370,
        available_hours_per_day=8,
        exam_year=2026,
        notes="希望冲击名校",
    )
    db_session.add(profile)
    db_session.commit()
    db_session.refresh(profile)
    return profile
