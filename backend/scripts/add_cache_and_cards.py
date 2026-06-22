"""Migration: add recommendation_cache and score_cards tables."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text
from app.db.database import engine, SessionLocal

TABLES = {
    "recommendation_cache": """
        CREATE TABLE IF NOT EXISTS recommendation_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            profile_id INTEGER NOT NULL,
            params_hash VARCHAR(64) NOT NULL UNIQUE,
            result_json TEXT NOT NULL,
            created_at DATE DEFAULT (date('now'))
        )
    """,
    "score_cards": """
        CREATE TABLE IF NOT EXISTS score_cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            school_name VARCHAR(100) NOT NULL,
            major_name VARCHAR(100) NOT NULL,
            major_code VARCHAR(10) NOT NULL,
            exam_subjects TEXT,
            score_data_json TEXT NOT NULL,
            created_at DATE DEFAULT (date('now'))
        )
    """,
}


def run():
    with engine.connect() as conn:
        for name, sql in TABLES.items():
            result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name=:n"), {"n": name})
            if result.fetchone():
                print(f"[SKIP] {name} already exists")
            else:
                conn.execute(text(sql))
                conn.commit()
                print(f"[OK] {name} created")


if __name__ == "__main__":
    run()
