"""Add preference_weights column to user_profiles table."""
import sqlite3
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings

db_path = settings.database_url.replace("sqlite:///", "")
if not os.path.isabs(db_path):
    db_path = os.path.join(os.path.dirname(__file__), "..", db_path)
db_path = os.path.normpath(db_path)

conn = sqlite3.connect(db_path)
try:
    conn.execute("ALTER TABLE user_profiles ADD COLUMN preference_weights TEXT")
    conn.commit()
    print("OK: Added preference_weights column to user_profiles")
except sqlite3.OperationalError as e:
    if "duplicate column" in str(e).lower():
        print("SKIP: preference_weights column already exists")
    else:
        print(f"ERROR: {e}")
        sys.exit(1)
finally:
    conn.close()
