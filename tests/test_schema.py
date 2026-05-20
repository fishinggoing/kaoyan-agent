# tests/test_schema.py
import sqlite3
import pytest
from kaoyan_agent.db.schema import create_tables


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    create_tables(conn)
    yield conn
    conn.close()


def test_schools_table_exists(db):
    cursor = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='schools'")
    assert cursor.fetchone() is not None


def test_schools_columns(db):
    db.execute("""
        INSERT INTO schools (name, tier, province, city, type, website)
        VALUES ('北京大学', '985', '北京', '北京', '综合', 'https://example.com')
    """)
    row = db.execute("SELECT * FROM schools WHERE name='北京大学'").fetchone()
    assert row['tier'] == '985'
    assert row['province'] == '北京'


def test_majors_table_exists(db):
    cursor = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='majors'")
    assert cursor.fetchone() is not None


def test_admission_scores_table_exists(db):
    cursor = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='admission_scores'")
    assert cursor.fetchone() is not None


def test_admitted_scores_table_exists(db):
    cursor = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='admitted_scores'")
    assert cursor.fetchone() is not None


def test_employment_quality_table_exists(db):
    cursor = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='employment_quality'")
    assert cursor.fetchone() is not None


def test_foreign_key_major_to_school(db):
    db.execute("INSERT INTO schools (name, tier, province, city, type) VALUES ('清华', '985', '北京', '北京', '综合')")
    school_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    db.execute(
        "INSERT INTO majors (school_id, name, discipline_rank, exam_subjects) VALUES (?, ?, ?, ?)",
        (school_id, '计算机科学', 'A+', '["政治","英语","数学一","408"]')
    )
    row = db.execute("SELECT * FROM majors WHERE school_id=?", (school_id,)).fetchone()
    assert row['name'] == '计算机科学'
