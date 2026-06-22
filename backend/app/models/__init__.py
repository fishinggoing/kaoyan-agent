from datetime import date, datetime
from sqlalchemy import String, Integer, Float, Date, Text, ForeignKey, Enum as SAEnum, DateTime, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.db.database import Base


class SchoolCategory(str, enum.Enum):
    ADULT_EDU = "成人本科"
    ASSOCIATE_UPGRADE = "专升本高校"
    GRAD_EXAM = "考研高校"


class SchoolLevel(str, enum.Enum):
    C9 = "C9"
    NINE_EIGHT_FIVE = "985"
    TWO_ONE_ONE = "211"
    DOUBLE_FIRST_CLASS = "双一流"
    MILITARY = "军事院校"
    SINO_FOREIGN = "中外合作"
    REGULAR = "普本"


class SchoolType(str, enum.Enum):
    COMPREHENSIVE = "综合"
    SCIENCE_ENGINEERING = "理工"
    NORMAL = "师范"
    FINANCE_ECONOMICS = "财经"
    AGRICULTURE = "农林"
    MEDICAL = "医药"
    LANGUAGE_LAW = "文法"
    ART_SPORTS = "艺体"
    MILITARY = "军事"
    RESEARCH = "科研"


class School(Base):
    __tablename__ = "schools"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    province: Mapped[str | None] = mapped_column(String(50))
    city: Mapped[str | None] = mapped_column(String(50))
    level: Mapped[SchoolLevel] = mapped_column(SAEnum(SchoolLevel), nullable=False, default=SchoolLevel.REGULAR)
    category: Mapped[SchoolCategory | None] = mapped_column(SAEnum(SchoolCategory), nullable=True)
    school_type: Mapped[SchoolType | None] = mapped_column(SAEnum(SchoolType), nullable=True)
    is_985: Mapped[bool] = mapped_column(Boolean, default=False)
    is_211: Mapped[bool] = mapped_column(Boolean, default=False)
    is_double_first: Mapped[bool] = mapped_column(Boolean, default=False)
    is_graduate_school: Mapped[bool] = mapped_column(default=False)
    website: Mapped[str | None] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    ranking_national: Mapped[int | None] = mapped_column(Integer)
    graduate_school_url: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[date] = mapped_column(Date, default=date.today)

    school_majors = relationship("SchoolMajor", back_populates="school")
    colleges = relationship("College", back_populates="school")


class College(Base):
    __tablename__ = "colleges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    school_id: Mapped[int] = mapped_column(Integer, ForeignKey("schools.id"), nullable=False)
    website: Mapped[str | None] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[date] = mapped_column(Date, default=date.today)

    school = relationship("School", back_populates="colleges")


class DegreeLevel(str, enum.Enum):
    MASTER = "硕士"
    DOCTOR = "博士"


class Major(Base):
    __tablename__ = "majors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[str | None] = mapped_column(String(50))
    discipline: Mapped[str | None] = mapped_column(String(100))
    degree_type: Mapped[str | None] = mapped_column(String(10))

    school_majors = relationship("SchoolMajor", back_populates="major")


class ScoreLine(Base):
    """DEPRECATED: Legacy score lines table — kept for code compatibility, no new data."""
    __tablename__ = "score_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_id: Mapped[int] = mapped_column(Integer, ForeignKey("schools.id"), nullable=False, index=True)
    major_code: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(10), nullable=False)
    total_score: Mapped[int] = mapped_column(Integer, nullable=False)
    politics_score: Mapped[int | None] = mapped_column(Integer)
    english_score: Mapped[int | None] = mapped_column(Integer)
    business_score_1: Mapped[int | None] = mapped_column(Integer)
    business_score_2: Mapped[int | None] = mapped_column(Integer)
    applicant_count: Mapped[int | None] = mapped_column(Integer)
    admit_count: Mapped[int | None] = mapped_column(Integer)
    is_national_line: Mapped[bool] = mapped_column(default=False)
    re_exam_total_score: Mapped[int | None] = mapped_column(Integer)
    re_exam_politics_score: Mapped[int | None] = mapped_column(Integer)
    re_exam_english_score: Mapped[int | None] = mapped_column(Integer)
    re_exam_business_score_1: Mapped[int | None] = mapped_column(Integer)
    re_exam_business_score_2: Mapped[int | None] = mapped_column(Integer)


class SchoolMajor(Base):
    """学校开设的某个具体专业 — 包含院系、方向、考试科目、招生人数"""
    __tablename__ = "school_majors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_id: Mapped[int] = mapped_column(Integer, ForeignKey("schools.id"), nullable=False, index=True)
    major_id: Mapped[int] = mapped_column(Integer, ForeignKey("majors.id"), nullable=False, index=True)

    department: Mapped[str | None] = mapped_column(String(200))
    direction: Mapped[str | None] = mapped_column(String(300))
    study_mode: Mapped[str | None] = mapped_column(String(20))

    exam_politics: Mapped[str | None] = mapped_column(String(100))
    exam_english: Mapped[str | None] = mapped_column(String(100))
    exam_math: Mapped[str | None] = mapped_column(String(100))
    exam_course1_name: Mapped[str | None] = mapped_column(String(200))
    exam_course1_code: Mapped[str | None] = mapped_column(String(20))
    exam_course2_name: Mapped[str | None] = mapped_column(String(200))
    exam_course2_code: Mapped[str | None] = mapped_column(String(20))
    exam_course3_name: Mapped[str | None] = mapped_column(String(200))
    exam_course3_code: Mapped[str | None] = mapped_column(String(20))
    exam_notes: Mapped[str | None] = mapped_column(Text)

    planned_enrollment: Mapped[int | None] = mapped_column(Integer)
    push_free_count: Mapped[int | None] = mapped_column(Integer)
    year: Mapped[int | None] = mapped_column(Integer)
    data_source: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    school = relationship("School", back_populates="school_majors")
    major = relationship("Major", back_populates="school_majors")


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    client_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    nickname: Mapped[str] = mapped_column(String(50), nullable=False)
    undergraduate_school: Mapped[str | None] = mapped_column(String(100))
    undergraduate_major: Mapped[str | None] = mapped_column(String(100))
    target_province: Mapped[str | None] = mapped_column(String(50))
    target_level: Mapped[str | None] = mapped_column(String(50))
    estimated_score: Mapped[int | None] = mapped_column(Integer)
    available_hours_per_day: Mapped[int | None] = mapped_column(Integer)
    exam_year: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)
    exam_config: Mapped[str | None] = mapped_column(Text)
    subject_strengths: Mapped[str | None] = mapped_column(Text)
    preference_weights: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[date] = mapped_column(Date, default=date.today)


class RecommendationCache(Base):
    __tablename__ = "recommendation_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    params_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    result_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[date] = mapped_column(Date, default=date.today)


class ScoreCard(Base):
    __tablename__ = "score_cards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    client_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    school_name: Mapped[str] = mapped_column(String(100), nullable=False)
    major_name: Mapped[str] = mapped_column(String(100), nullable=False)
    major_code: Mapped[str] = mapped_column(String(10), nullable=False)
    exam_subjects: Mapped[str | None] = mapped_column(Text)
    score_data_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[date] = mapped_column(Date, default=date.today)


class DisciplineRatingEnum(str, enum.Enum):
    A_PLUS = "A+"
    A = "A"
    A_MINUS = "A-"
    B_PLUS = "B+"
    B = "B"
    B_MINUS = "B-"
    C_PLUS = "C+"
    C = "C"
    C_MINUS = "C-"


class DisciplineRating(Base):
    __tablename__ = "discipline_ratings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    discipline_code: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    discipline_name: Mapped[str] = mapped_column(String(100), nullable=False)
    school_name: Mapped[str] = mapped_column(String(100), nullable=False)
    school_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("schools.id"), nullable=True)
    rating: Mapped[DisciplineRatingEnum] = mapped_column(SAEnum(DisciplineRatingEnum), nullable=False)
    created_at: Mapped[date] = mapped_column(Date, default=date.today)
