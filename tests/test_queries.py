# tests/test_queries.py
import sqlite3
import pytest
from kaoyan_agent.db.schema import create_tables
from kaoyan_agent.db.queries import (
    search_schools,
    get_majors,
    query_scores,
    get_employment,
    compare_schools,
    query_admitted_scores,
)


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    create_tables(conn)
    _seed(conn)
    yield conn
    conn.close()


def _seed(conn):
    conn.execute(
        "INSERT INTO schools (name, tier, province, city, type) VALUES (?,?,?,?,?)",
        ("浙江大学", "985", "浙江", "杭州", "综合"),
    )
    conn.execute(
        "INSERT INTO schools (name, tier, province, city, type) VALUES (?,?,?,?,?)",
        ("南京大学", "985", "江苏", "南京", "综合"),
    )
    conn.execute(
        "INSERT INTO schools (name, tier, province, city, type) VALUES (?,?,?,?,?)",
        ("杭州电子科技大学", "双非", "浙江", "杭州", "理工"),
    )
    zju = conn.execute("SELECT id FROM schools WHERE name='浙江大学'").fetchone()[0]
    nju = conn.execute("SELECT id FROM schools WHERE name='南京大学'").fetchone()[0]
    hdu = conn.execute("SELECT id FROM schools WHERE name='杭州电子科技大学'").fetchone()[0]

    conn.execute(
        "INSERT INTO majors (school_id, name, discipline_rank, exam_subjects) VALUES (?,?,?,?)",
        (zju, "计算机科学与技术", "A+", '["政治","英语","数学一","408"]'),
    )
    conn.execute(
        "INSERT INTO majors (school_id, name, discipline_rank, exam_subjects) VALUES (?,?,?,?)",
        (nju, "计算机科学与技术", "A", '["政治","英语","数学一","408"]'),
    )
    conn.execute(
        "INSERT INTO majors (school_id, name, discipline_rank, exam_subjects) VALUES (?,?,?,?)",
        (hdu, "计算机科学与技术", "B+", '["政治","英语","数学一","408"]'),
    )
    conn.execute(
        "INSERT INTO majors (school_id, name, discipline_rank, exam_subjects) VALUES (?,?,?,?)",
        (zju, "软件工程", "A+", '["政治","英语","数学一","878"]'),
    )

    zju_cs = conn.execute(
        "SELECT id FROM majors WHERE school_id=? AND name='计算机科学与技术'", (zju,)
    ).fetchone()[0]
    nju_cs = conn.execute(
        "SELECT id FROM majors WHERE school_id=? AND name='计算机科学与技术'", (nju,)
    ).fetchone()[0]
    hdu_cs = conn.execute(
        "SELECT id FROM majors WHERE school_id=? AND name='计算机科学与技术'", (hdu,)
    ).fetchone()[0]

    conn.execute(
        "INSERT INTO admission_scores (major_id, year, admission_line, applicants, enrolled, push_free_ratio) VALUES (?,?,?,?,?,?)",
        (zju_cs, 2025, 380, 1200, 45, 0.6),
    )
    conn.execute(
        "INSERT INTO admission_scores (major_id, year, admission_line, applicants, enrolled, push_free_ratio) VALUES (?,?,?,?,?,?)",
        (nju_cs, 2025, 370, 900, 50, 0.55),
    )
    conn.execute(
        "INSERT INTO admission_scores (major_id, year, admission_line, applicants, enrolled, push_free_ratio) VALUES (?,?,?,?,?,?)",
        (hdu_cs, 2025, 310, 600, 80, 0.2),
    )

    conn.execute(
        "INSERT INTO admitted_scores (major_id, year, lowest_score, avg_score, highest_score) VALUES (?,?,?,?,?)",
        (zju_cs, 2025, 370, 385, 400),
    )

    conn.execute(
        "INSERT INTO employment_quality (school_id, year, employment_rate, avg_salary, summary) VALUES (?,?,?,?,?)",
        (zju, 2024, 0.98, 250000, "浙江大学计算机就业集中在杭州互联网企业"),
    )
    conn.execute(
        "INSERT INTO employment_quality (school_id, year, employment_rate, avg_salary, summary) VALUES (?,?,?,?,?)",
        (nju, 2024, 0.97, 260000, "南京大学毕业生多去上海/南京"),
    )
    conn.commit()


def test_search_schools_by_province(db):
    results = search_schools(db, province="浙江")
    names = [r["name"] for r in results]
    assert "浙江大学" in names
    assert "杭州电子科技大学" in names
    assert "南京大学" not in names


def test_search_schools_by_tier(db):
    results = search_schools(db, tier="985")
    names = [r["name"] for r in results]
    assert "浙江大学" in names
    assert "南京大学" in names
    assert len(names) == 2


def test_search_schools_combined(db):
    results = search_schools(db, province="浙江", tier="985")
    names = [r["name"] for r in results]
    assert names == ["浙江大学"]


def test_get_majors(db):
    zju = db.execute("SELECT id FROM schools WHERE name='浙江大学'").fetchone()[0]
    results = get_majors(db, school_id=zju)
    names = [r["name"] for r in results]
    assert "计算机科学与技术" in names
    assert "软件工程" in names


def test_query_scores(db):
    zju = db.execute("SELECT id FROM schools WHERE name='浙江大学'").fetchone()[0]
    zju_cs = db.execute(
        "SELECT id FROM majors WHERE school_id=? AND name='计算机科学与技术'", (zju,)
    ).fetchone()[0]
    results = query_scores(db, major_id=zju_cs)
    latest = results[0]
    assert latest["admission_line"] == 380
    assert latest["applicants"] == 1200


def test_get_employment(db):
    zju = db.execute("SELECT id FROM schools WHERE name='浙江大学'").fetchone()[0]
    results = get_employment(db, school_id=zju)
    assert len(results) > 0
    assert results[0]["employment_rate"] == 0.98


def test_compare_schools(db):
    zju = db.execute("SELECT id FROM schools WHERE name='浙江大学'").fetchone()[0]
    nju = db.execute("SELECT id FROM schools WHERE name='南京大学'").fetchone()[0]
    results = compare_schools(db, [zju, nju], "计算机科学与技术")
    assert len(results) == 2
    assert results[0]["school_name"] == "浙江大学"
    assert results[1]["school_name"] == "南京大学"
    assert results[0]["tier"] == "985"
    assert "admission_line" in results[0].keys()


def test_query_admitted_scores(db):
    zju = db.execute("SELECT id FROM schools WHERE name='浙江大学'").fetchone()[0]
    zju_cs = db.execute(
        "SELECT id FROM majors WHERE school_id=? AND name='计算机科学与技术'", (zju,)
    ).fetchone()[0]
    results = query_admitted_scores(db, major_id=zju_cs)
    assert len(results) > 0
    assert results[0]["lowest_score"] == 370
    assert results[0]["avg_score"] == 385
    assert results[0]["highest_score"] == 400
