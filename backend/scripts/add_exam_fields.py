"""
Add exam_config and subject_strengths columns to user_profiles table.

Usage: python -m scripts.add_exam_fields
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text
from app.db.database import engine


def add_exam_fields():
    with engine.connect() as conn:
        # Check if columns already exist
        result = conn.execute(text("PRAGMA table_info(user_profiles)"))
        existing = [row[1] for row in result.fetchall()]

        if "exam_config" not in existing:
            conn.execute(text("ALTER TABLE user_profiles ADD COLUMN exam_config TEXT"))
            print("Added exam_config column")
        else:
            print("exam_config column already exists")

        if "subject_strengths" not in existing:
            conn.execute(text("ALTER TABLE user_profiles ADD COLUMN subject_strengths TEXT"))
            print("Added subject_strengths column")
        else:
            print("subject_strengths column already exists")

        conn.commit()
        print("Migration complete")


if __name__ == "__main__":
    add_exam_fields()
