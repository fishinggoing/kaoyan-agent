"""Create discipline_ratings table for storing 教育部第四轮学科评估 data."""

import sqlite3
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.config import settings

db_path = settings.database_url.replace("sqlite:///", "")
if not os.path.isabs(db_path):
    db_path = os.path.join(os.path.dirname(__file__), "..", db_path)
db_path = os.path.normpath(db_path)

print(f"Using database: {db_path}")

conn = sqlite3.connect(db_path)
try:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS discipline_ratings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            discipline_code VARCHAR(10) NOT NULL,
            discipline_name VARCHAR(100) NOT NULL,
            school_name VARCHAR(100) NOT NULL,
            school_id INTEGER REFERENCES schools(id),
            rating VARCHAR(3) NOT NULL,
            created_at DATE DEFAULT (DATE('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_discipline_ratings_code
            ON discipline_ratings(discipline_code);
        CREATE INDEX IF NOT EXISTS idx_discipline_ratings_school
            ON discipline_ratings(school_name);
    """)
    conn.commit()
    print("OK: Created discipline_ratings table and indexes")
except Exception as e:
    print(f"ERROR: {e}")
    sys.exit(1)
finally:
    conn.close()
