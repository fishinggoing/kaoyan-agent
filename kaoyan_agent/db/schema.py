# kaoyan_agent/db/schema.py
import sqlite3


def create_tables(conn: sqlite3.Connection):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS schools (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name VARCHAR(128) NOT NULL,
            tier VARCHAR(32) NOT NULL DEFAULT '',
            province VARCHAR(32) NOT NULL DEFAULT '',
            city VARCHAR(32) NOT NULL DEFAULT '',
            type VARCHAR(32) NOT NULL DEFAULT '',
            website VARCHAR(256) NOT NULL DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS majors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            school_id INTEGER NOT NULL REFERENCES schools(id),
            name VARCHAR(128) NOT NULL,
            discipline_rank VARCHAR(8) NOT NULL DEFAULT '',
            exam_subjects TEXT NOT NULL DEFAULT '[]'
        );

        CREATE TABLE IF NOT EXISTS admission_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            major_id INTEGER NOT NULL REFERENCES majors(id),
            year INTEGER NOT NULL,
            admission_line INTEGER,
            applicants INTEGER,
            enrolled INTEGER,
            push_free_ratio REAL
        );

        CREATE TABLE IF NOT EXISTS admitted_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            major_id INTEGER NOT NULL REFERENCES majors(id),
            year INTEGER NOT NULL,
            lowest_score INTEGER,
            avg_score INTEGER,
            highest_score INTEGER
        );

        CREATE TABLE IF NOT EXISTS employment_quality (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            school_id INTEGER NOT NULL REFERENCES schools(id),
            year INTEGER NOT NULL,
            employment_rate REAL,
            avg_salary INTEGER,
            summary TEXT NOT NULL DEFAULT ''
        );
    """)
    conn.commit()
