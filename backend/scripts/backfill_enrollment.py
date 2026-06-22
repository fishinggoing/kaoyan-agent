"""Stage 2: Backfill year, planned_enrollment, push_free_count from score_lines.

Uses UPDATE FROM (SQLite 3.33+) with temp table + indexes for efficiency.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import sqlite3


def backfill():
    conn = sqlite3.connect("gradschool.db")
    conn.execute("PRAGMA journal_mode=WAL")

    try:
        null_count = conn.execute(
            "SELECT COUNT(*) FROM school_majors WHERE planned_enrollment IS NULL"
        ).fetchone()[0]
        print(f"Rows with NULL planned_enrollment: {null_count}")

        if null_count == 0:
            print("All rows already have enrollment data.")
            return

        # Step 1: Create aggregate temp table from score_lines
        print("Creating enrollment aggregates...")
        conn.executescript("""
            DROP TABLE IF EXISTS _tmp_enroll;
            CREATE TEMP TABLE _tmp_enroll (
                school_id INTEGER,
                major_code TEXT,
                latest_year INTEGER,
                total_admit INTEGER,
                total_applicant INTEGER
            );
            INSERT INTO _tmp_enroll
            SELECT
                school_id,
                major_code,
                MAX(year),
                SUM(COALESCE(admit_count, 0)),
                SUM(COALESCE(applicant_count, 0))
            FROM score_lines
            WHERE school_id IS NOT NULL AND major_code IS NOT NULL
            GROUP BY school_id, major_code;
            CREATE INDEX _tmp_e_idx ON _tmp_enroll(school_id, major_code);
        """)
        conn.commit()
        agg_count = conn.execute("SELECT COUNT(*) FROM _tmp_enroll").fetchone()[0]
        print(f"Aggregate rows: {agg_count}")

        # Step 2: UPDATE FROM join (SQLite 3.33+ syntax)
        print("Updating school_majors...")
        conn.executescript("""
            UPDATE school_majors
            SET
                year = e.latest_year,
                planned_enrollment = e.total_admit,
                push_free_count = e.total_applicant
            FROM _tmp_enroll e
            JOIN majors m ON m.code = e.major_code
            WHERE school_majors.school_id = e.school_id
              AND school_majors.major_id = m.id
        """)
        conn.commit()

        # Step 3: Verify
        still_null = conn.execute(
            "SELECT COUNT(*) FROM school_majors WHERE planned_enrollment IS NULL"
        ).fetchone()[0]
        updated = null_count - still_null

        with_enrollment = conn.execute(
            "SELECT COUNT(*) FROM school_majors WHERE planned_enrollment > 0"
        ).fetchone()[0]
        zero_enrollment = conn.execute(
            "SELECT COUNT(*) FROM school_majors WHERE planned_enrollment = 0"
        ).fetchone()[0]

        print(f"Updated: {updated}, Still NULL: {still_null}")
        print(f"With enrollment > 0: {with_enrollment}")
        print(f"With enrollment = 0: {zero_enrollment}")

        # Sample
        samples = conn.execute("""
            SELECT s.name, m.name, sm.year, sm.planned_enrollment, sm.push_free_count
            FROM school_majors sm
            JOIN schools s ON s.id = sm.school_id
            JOIN majors m ON m.id = sm.major_id
            WHERE sm.planned_enrollment > 0
            LIMIT 5
        """).fetchall()
        if samples:
            print("Samples (with enrollment > 0):")
            for row in samples:
                print(f"  {row[0]} — {row[1]} (year={row[2]}, enroll={row[3]}, push_free={row[4]})")
        else:
            print("No rows with enrollment > 0 (all have admit_count=0 in score_lines)")

        conn.execute("DROP TABLE IF EXISTS _tmp_enroll")
        conn.commit()
        print("\nStage 2 complete!")

    except Exception as e:
        conn.rollback()
        print(f"ERROR: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    backfill()
