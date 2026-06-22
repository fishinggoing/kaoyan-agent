"""Tests for business logic services."""

import pytest
from app.services.school_service import (
    list_schools, search_schools, get_school, create_school, update_school, delete_school,
)
from app.services.score_service import list_school_majors, get_school_major_detail, get_school_enrollment_summary
from app.services.profile_service import (
    create_profile, get_profile, update_profile,
)
from app.utils.exceptions import NotFoundError
from app.models import SchoolMajor


class TestSchoolService:
    def test_list_all_schools(self, db_session, sample_schools):
        items, total = list_schools(db_session)
        assert total == 4
        assert len(items) == 4

    def test_list_schools_by_province(self, db_session, sample_schools):
        items, total = list_schools(db_session, province="北京")
        assert total == 1
        assert items[0].name == "北京大学"

    def test_list_schools_by_name_search(self, db_session, sample_schools):
        items, total = list_schools(db_session, name="浙江")
        assert total == 1
        assert items[0].name == "浙江大学"

    def test_list_schools_by_level(self, db_session, sample_schools):
        items, total = list_schools(db_session, level="C9")
        # 北京大学, 浙江大学 are C9 in the fixture
        assert total >= 1

    def test_list_schools_pagination(self, db_session, sample_schools):
        items, total = list_schools(db_session, page=1, size=2)
        assert len(items) == 2
        assert total == 4

    def test_get_school(self, db_session, sample_school):
        school = get_school(db_session, sample_school.id)
        assert school.name == "清华大学"

    def test_get_school_not_found(self, db_session):
        with pytest.raises(NotFoundError):
            get_school(db_session, 99999)

    def test_create_school(self, db_session):
        school = create_school(db_session, {
            "name": "南京大学",
            "province": "江苏",
            "city": "南京",
            "level": "C9",
            "school_type": "综合",
            "is_graduate_school": True,
            "ranking_national": 6,
        })
        assert school.id is not None
        assert school.name == "南京大学"

    def test_update_school(self, db_session, sample_school):
        updated = update_school(db_session, sample_school.id, {
            "description": "更新后的描述",
        })
        assert updated.description == "更新后的描述"

    def test_delete_school(self, db_session, sample_school):
        school_id = sample_school.id
        delete_school(db_session, school_id)
        with pytest.raises(NotFoundError):
            get_school(db_session, school_id)


class TestSearchSchools:
    def test_search_by_name(self, db_session, sample_schools):
        items, total = search_schools(db_session, "浙江")
        assert total == 1
        assert items[0]["name"] == "浙江大学"
        assert items[0]["relevance"] >= 1

    def test_search_by_province(self, db_session, sample_schools):
        items, total = search_schools(db_session, "湖北")
        assert total == 1
        assert items[0]["name"] == "武汉大学"

    def test_search_by_description(self, db_session, sample_school):
        items, total = search_schools(db_session, "顶尖")
        assert total >= 1

    def test_search_empty_query(self, db_session, sample_schools):
        items, total = search_schools(db_session, "")
        assert total >= 4

    def test_search_no_results(self, db_session, sample_schools):
        items, total = search_schools(db_session, "火星大学")
        assert total == 0
        assert items == []

    def test_search_pagination(self, db_session, sample_schools):
        items, total = search_schools(db_session, "大学", page=1, size=2)
        assert len(items) <= 2
        assert total >= 4

    def test_search_relevance_ordering(self, db_session, sample_schools):
        items, _ = search_schools(db_session, "深圳")
        assert len(items) >= 1
        assert items[0]["name"] == "深圳大学"  # exact name match has highest relevance


class TestSchoolMajorService:
    def test_list_school_majors(self, db_session, sample_school, sample_major):
        # sample_major fixture creates a SchoolMajor for sample_school
        items, total = list_school_majors(db_session)
        assert total >= 1

    def test_list_school_majors_by_school(self, db_session, sample_school, sample_major):
        items, total = list_school_majors(db_session, school_id=sample_school.id)
        assert total >= 1
        if items:
            assert items[0]["school_name"] == "清华大学"

    def test_enrollment_summary(self, db_session, sample_school, sample_major):
        result = get_school_enrollment_summary(db_session, sample_school.id)
        assert result["school_id"] == sample_school.id
        assert "total_planned_enrollment" in result


class TestProfileService:
    def test_create_profile(self, db_session):
        profile = create_profile(db_session, {
            "nickname": "新考生",
            "estimated_score": 390,
            "available_hours_per_day": 6,
            "exam_year": 2026,
        }, client_id="test-service-cid")
        assert profile.id is not None
        assert profile.nickname == "新考生"

    def test_get_profile(self, db_session, sample_profile):
        profile = get_profile(db_session, sample_profile.id, sample_profile.client_id)
        assert profile.nickname == "测试考生"

    def test_get_profile_not_found(self, db_session):
        with pytest.raises(NotFoundError):
            get_profile(db_session, 99999, "nonexistent-client")

    def test_update_profile(self, db_session, sample_profile):
        updated = update_profile(db_session, sample_profile.id, {
            "notes": "更新备注",
        }, client_id=sample_profile.client_id)
        assert updated.notes == "更新备注"
