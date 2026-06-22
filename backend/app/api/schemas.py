"""Pydantic request/response schemas for API validation."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ── Generic Response Wrappers ──

class ApiResponse(BaseModel):
    success: bool
    data: Any | None = None
    error: str | None = None


class PaginatedData(BaseModel):
    items: list[Any]
    total: int
    page: int = 1
    size: int = 20


# ── Profile Schemas ──

class ProfileCreate(BaseModel):
    nickname: str = Field(..., min_length=1, description="考生昵称")
    undergraduate_school: str | None = None
    undergraduate_major: str | None = None
    target_province: str | None = None
    target_level: str | None = None
    estimated_score: int | None = Field(None, ge=0, le=750)
    available_hours_per_day: int | None = Field(None, ge=0, le=24)
    exam_year: int | None = None
    notes: str | None = None
    exam_config: str | None = Field(None, description="JSON string of exam subjects")
    subject_strengths: str | None = Field(None, description="JSON string of subject strength ratings")


class ProfileUpdate(BaseModel):
    nickname: str | None = Field(None, min_length=1)
    undergraduate_school: str | None = None
    undergraduate_major: str | None = None
    target_province: str | None = None
    target_level: str | None = None
    estimated_score: int | None = Field(None, ge=0, le=750)
    available_hours_per_day: int | None = Field(None, ge=0, le=24)
    exam_year: int | None = None
    notes: str | None = None
    exam_config: str | None = None


# ── School Schemas ──

class SchoolCreate(BaseModel):
    name: str = Field(..., min_length=1)
    province: str = ""
    city: str = ""
    level: str = "普通"
    school_type: str = "综合"
    is_graduate_school: bool = False
    website: str | None = None
    description: str | None = None
    ranking_national: int | None = None


class SchoolUpdate(BaseModel):
    name: str | None = Field(None, min_length=1)
    province: str | None = None
    city: str | None = None
    level: str | None = None
    school_type: str | None = None
    is_graduate_school: bool | None = None
    website: str | None = None
    description: str | None = None
    ranking_national: int | None = None


# ── Decision / Recommendation Schemas ──

class DecisionRequest(BaseModel):
    profile_id: int = Field(..., gt=0)
    target_province: str | None = None
    target_level: str | None = None
    major_keyword: str | None = None


class DecisionFromChatRequest(BaseModel):
    profile_id: int = Field(..., gt=0)
    school_names: list[str] = Field(..., min_length=1)
    target_province: str | None = None
    target_level: str | None = None
    major_keyword: str | None = None


class AnalyzeRequest(BaseModel):
    school_id: int = Field(..., gt=0)
    major_code: str = Field(..., min_length=1)
    estimated_score: int | None = None


# ── Score Card Schemas ──

class ScoreCardCreate(BaseModel):
    school_name: str = Field(..., min_length=1)
    major_name: str = Field(..., min_length=1)
    major_code: str = Field(..., min_length=1)
    exam_subjects: list[str] = []
    score_data: list[dict[str, Any]] = Field(default_factory=list)


# ── Needs Analysis Schemas ──

class NeedsChatRequest(BaseModel):
    profile_id: int = Field(..., gt=0)
    message: str = Field(..., min_length=1)
    history: list[dict[str, str]] = Field(default_factory=list)


class NeedsFinalizeRequest(BaseModel):
    profile_id: int = Field(..., gt=0)
    history: list[dict[str, str]] = Field(default_factory=list)


# ── Weights Save Schema ──

class SaveWeightsRequest(BaseModel):
    weights: dict[str, Any] = Field(..., description="Preference weights object from needs analysis")


