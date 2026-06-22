"""Migration: add has_graduate column to majors table.

Usage: python scripts/add_has_graduate.py [--mark-via-scores]

  --mark-via-scores   Mark school+major_code combos that have score_lines as confirmed.
                      NOTE: only useful once score_lines contain real (not synthetic) data.

Without the flag, the script only adds the column (all values remain NULL = unknown).
"""

import argparse
import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "gradschool.db")


def migrate(mark_via_scores: bool = False):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Add column
    try:
        cur.execute("ALTER TABLE majors ADD COLUMN has_graduate BOOLEAN DEFAULT NULL")
        print("ADDED column has_graduate")
    except sqlite3.OperationalError as e:
        if "duplicate column" in str(e).lower():
            print("Column exists, skipping ALTER")
        else:
            raise

    if mark_via_scores:
        cur.execute("""
            UPDATE majors SET has_graduate = 1
            WHERE (school_id, code) IN (
                SELECT DISTINCT school_id, major_code FROM score_lines
            )
        """)
        print(f"Marked {cur.rowcount} majors via score_lines")

    # Stats
    cur.execute("SELECT has_graduate, COUNT(*) FROM majors GROUP BY has_graduate")
    rows = cur.fetchall()
    total = sum(cnt for _, cnt in rows)
    labels = {None: "Unknown", 1: "Confirmed", 0: "Not recruiting"}
    for val, cnt in rows:
        pct = 100 * cnt / total if total > 0 else 0
        print(f"  {labels[val]}: {cnt} ({pct:.1f}%)")

    conn.commit()
    conn.close()
    print("Done.")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--mark-via-scores", action="store_true")
    migrate(**vars(p.parse_args()))
