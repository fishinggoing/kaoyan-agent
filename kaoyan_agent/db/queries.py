# kaoyan_agent/db/queries.py
import sqlite3
from typing import Optional


def search_schools(
    conn: sqlite3.Connection,
    province: Optional[str] = None,
    tier: Optional[str] = None,
    type: Optional[str] = None,
    keyword: Optional[str] = None,
) -> list[dict]:
    query = "SELECT * FROM schools WHERE 1=1"
    params = []
    if province:
        query += " AND province = ?"
        params.append(province)
    if tier:
        query += " AND tier = ?"
        params.append(tier)
    if type:
        query += " AND type = ?"
        params.append(type)
    if keyword:
        query += " AND name LIKE ?"
        params.append(f"%{keyword}%")
    cursor = conn.execute(query, params)
    return [dict(row) for row in cursor.fetchall()]


def get_majors(
    conn: sqlite3.Connection,
    school_id: Optional[int] = None,
    discipline: Optional[str] = None,
) -> list[dict]:
    query = """
        SELECT m.*, s.name as school_name
        FROM majors m JOIN schools s ON m.school_id = s.id
        WHERE 1=1
    """
    params = []
    if school_id:
        query += " AND m.school_id = ?"
        params.append(school_id)
    if discipline:
        query += " AND m.name LIKE ?"
        params.append(f"%{discipline}%")
    cursor = conn.execute(query, params)
    return [dict(row) for row in cursor.fetchall()]


def query_scores(
    conn: sqlite3.Connection,
    major_id: Optional[int] = None,
    year: Optional[int] = None,
) -> list[dict]:
    query = """
        SELECT a.*, m.name as major_name, s.name as school_name
        FROM admission_scores a
        JOIN majors m ON a.major_id = m.id
        JOIN schools s ON m.school_id = s.id
        WHERE 1=1
    """
    params = []
    if major_id:
        query += " AND a.major_id = ?"
        params.append(major_id)
    if year:
        query += " AND a.year = ?"
        params.append(year)
    query += " ORDER BY a.year DESC"
    cursor = conn.execute(query, params)
    return [dict(row) for row in cursor.fetchall()]


def query_admitted_scores(
    conn: sqlite3.Connection,
    major_id: Optional[int] = None,
    year: Optional[int] = None,
) -> list[dict]:
    query = """
        SELECT a.*, m.name as major_name, s.name as school_name
        FROM admitted_scores a
        JOIN majors m ON a.major_id = m.id
        JOIN schools s ON m.school_id = s.id
        WHERE 1=1
    """
    params = []
    if major_id:
        query += " AND a.major_id = ?"
        params.append(major_id)
    if year:
        query += " AND a.year = ?"
        params.append(year)
    query += " ORDER BY a.year DESC"
    cursor = conn.execute(query, params)
    return [dict(row) for row in cursor.fetchall()]


def get_employment(
    conn: sqlite3.Connection,
    school_id: Optional[int] = None,
) -> list[dict]:
    query = """
        SELECT e.*, s.name as school_name
        FROM employment_quality e
        JOIN schools s ON e.school_id = s.id
        WHERE 1=1
    """
    params = []
    if school_id:
        query += " AND e.school_id = ?"
        params.append(school_id)
    query += " ORDER BY e.year DESC"
    cursor = conn.execute(query, params)
    return [dict(row) for row in cursor.fetchall()]


def compare_schools(
    conn: sqlite3.Connection,
    school_ids: list[int],
    major_name: str,
) -> list[dict]:
    placeholders = ",".join("?" for _ in school_ids)
    query = f"""
        SELECT s.id as school_id, s.name as school_name, s.tier, s.province, s.city,
               m.name as major_name, m.discipline_rank,
               a.year, a.admission_line, a.applicants, a.enrolled, a.push_free_ratio
        FROM schools s
        JOIN majors m ON m.school_id = s.id
        LEFT JOIN admission_scores a ON a.major_id = m.id
        WHERE s.id IN ({placeholders})
          AND m.name = ?
        ORDER BY s.id, a.year DESC
    """
    params = [*school_ids, major_name]
    cursor = conn.execute(query, params)
    rows = cursor.fetchall()

    seen = {}
    result = []
    for row in rows:
        sid = row["school_id"]
        if sid not in seen:
            seen[sid] = dict(row)
            result.append(seen[sid])
    return result
