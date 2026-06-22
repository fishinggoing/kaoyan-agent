"""Tests for SQLAlchemy models and enums."""

from app.models import (
    School, SchoolLevel, SchoolType, SchoolCategory,
    Major, SchoolMajor, DegreeLevel,
    ScoreLine,
    UserProfile,
)


class TestSchoolLevel:
    def test_all_levels(self):
        assert SchoolLevel.C9.value == "C9"
        assert SchoolLevel.NINE_EIGHT_FIVE.value == "985"
        assert SchoolLevel.TWO_ONE_ONE.value == "211"
        assert SchoolLevel.DOUBLE_FIRST_CLASS.value == "双一流"
        assert SchoolLevel.MILITARY.value == "军事院校"
        assert SchoolLevel.SINO_FOREIGN.value == "中外合作"
        assert SchoolLevel.REGULAR.value == "普本"

    def test_level_count(self):
        assert len(SchoolLevel) == 7


class TestSchoolType:
    def test_all_types(self):
        assert SchoolType.COMPREHENSIVE.value == "综合"
        assert SchoolType.SCIENCE_ENGINEERING.value == "理工"
        assert len(SchoolType) == 10  # added MILITARY, RESEARCH

    def test_school_category(self):
        assert SchoolCategory.GRAD_EXAM.value == "考研高校"
        assert SchoolCategory.ADULT_EDU.value == "成人本科"
        assert SchoolCategory.ASSOCIATE_UPGRADE.value == "专升本高校"


class TestDegreeLevel:
    def test_degree_levels(self):
        assert DegreeLevel.MASTER.value == "硕士"
        assert DegreeLevel.DOCTOR.value == "博士"


class TestSchoolModel:
    def test_create_school(self, db_session):
        school = School(
            name="复旦大学",
            province="上海",
            city="上海",
            level=SchoolLevel.C9,
            school_type=SchoolType.COMPREHENSIVE,
            is_graduate_school=True,
            is_985=True,
            is_211=True,
            is_double_first=True,
            ranking_national=4,
        )
        db_session.add(school)
        db_session.commit()

        assert school.id is not None
        assert school.name == "复旦大学"
        assert school.province == "上海"
        assert school.level == SchoolLevel.C9
        assert school.is_985 is True

    def test_school_repr(self, sample_school):
        assert sample_school.name == "清华大学"
        assert sample_school.ranking_national == 1


class TestMajorModel:
    def test_create_major(self, db_session):
        major = Major(
            code="083500",
            name="软件工程",
            category="工学",
            discipline="软件工程",
            degree_type="学术学位",
        )
        db_session.add(major)
        db_session.commit()

        assert major.id is not None
        assert major.code == "083500"
        assert major.discipline == "软件工程"

    def test_major_school_relationship(self, sample_major, sample_school):
        # Major is linked to school via SchoolMajor junction (created in fixture)
        assert sample_major.name == "计算机科学与技术"
        assert sample_major.code == "081200"
        assert sample_major.discipline == "计算机科学与技术"


class TestSchoolMajorModel:
    def test_create_school_major(self, db_session, sample_school, sample_major):
        sm = SchoolMajor(
            school_id=sample_school.id,
            major_id=sample_major.id,
            department="计算机学院",
            direction="网络空间安全方向",
            study_mode="全日制",
            planned_enrollment=10,
            push_free_count=5,
            year=2026,
            exam_politics="101 思想政治理论",
            exam_english="201 英语(一)",
            exam_math="301 数学(一)",
        )
        db_session.add(sm)
        db_session.commit()

        assert sm.id is not None
        assert sm.planned_enrollment == 10
        assert sm.year == 2026

    def test_enrollment_zero(self, db_session, sample_school, sample_major):
        sm = SchoolMajor(
            school_id=sample_school.id,
            major_id=sample_major.id,
            planned_enrollment=0,
            study_mode="全日制",
            year=2026,
        )
        db_session.add(sm)
        db_session.commit()

        assert sm.planned_enrollment == 0


class TestScoreLineModel:
    def test_create_score_line(self, db_session, sample_school):
        line = ScoreLine(
            school_id=sample_school.id,
            major_code="081200",
            year=2025,
            category="学硕",
            total_score=360,
            applicant_count=500,
            admit_count=35,
        )
        db_session.add(line)
        db_session.commit()

        assert line.id is not None
        assert line.total_score == 360
        assert line.year == 2025


class TestUserProfileModel:
    def test_create_profile(self, db_session):
        profile = UserProfile(
            client_id="test-client-002",
            nickname="考研人",
            estimated_score=380,
            available_hours_per_day=6,
            exam_year=2026,
        )
        db_session.add(profile)
        db_session.commit()

        assert profile.id is not None
        assert profile.nickname == "考研人"

    def test_profile_defaults(self, sample_profile):
        assert sample_profile.undergraduate_school == "武汉理工大学"
        assert sample_profile.target_province == "北京"
        assert sample_profile.estimated_score == 370
