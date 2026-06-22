"""Populate school_majors table from score_lines data — staged approach.

Stage 1 (fast): Extract distinct (school_id, major_code) pairs, resolve
                 major_id, batch insert into school_majors.
Stage 2 (optional): Backfill year/enrollment from score_lines aggregation.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import sqlite3
import datetime


def populate():
    conn = sqlite3.connect("gradschool.db")

    try:
        # Step 1: Check existing
        count = conn.execute("SELECT COUNT(*) FROM school_majors").fetchone()[0]
        print(f"Existing school_majors rows: {count}")
        if count > 0:
            print("Truncating...")
            conn.execute("DELETE FROM school_majors")
            conn.commit()

        # Step 2: Extract distinct pairs into temp table
        print("Creating temp table with distinct (school_id, major_code) pairs...")
        conn.executescript("""
            DROP TABLE IF EXISTS _tmp_sm;
            CREATE TEMP TABLE _tmp_sm (
                school_id INTEGER,
                major_code TEXT
            );
            INSERT INTO _tmp_sm
            SELECT DISTINCT school_id, major_code
            FROM score_lines
            WHERE school_id IS NOT NULL AND major_code IS NOT NULL;
            CREATE INDEX _tmp_sm_idx ON _tmp_sm(major_code, school_id);
        """)
        conn.commit()
        pair_count = conn.execute("SELECT COUNT(*) FROM _tmp_sm").fetchone()[0]
        print(f"Distinct pairs: {pair_count}")

        # Step 3: Load major_code → major_id mapping
        print("Loading major code→id mapping...")
        majors = conn.execute(
            "SELECT code, id FROM majors WHERE code IS NOT NULL"
        ).fetchall()
        code_to_id = {code: mid for code, mid in majors}
        print(f"Loaded {len(code_to_id)} major codes")

        # Step 4: Batch insert
        print("Batch inserting...")
        now = datetime.datetime.utcnow().isoformat()

        BATCH = 10000
        offset = 0
        total_inserted = 0
        total_missed = 0

        while True:
            rows = conn.execute(
                "SELECT school_id, major_code FROM _tmp_sm ORDER BY school_id, major_code LIMIT ? OFFSET ?",
                (BATCH, offset)
            ).fetchall()
            if not rows:
                break

            to_insert = []
            for school_id, major_code in rows:
                major_id = code_to_id.get(major_code)
                if major_id is not None:
                    to_insert.append((school_id, major_id, "score_lines_migration", now))
                else:
                    total_missed += 1

            if to_insert:
                conn.executemany(
                    "INSERT INTO school_majors (school_id, major_id, data_source, created_at) VALUES (?, ?, ?, ?)",
                    to_insert
                )
                total_inserted += len(to_insert)

            offset += BATCH
            if offset % 100000 == 0:
                conn.commit()
                print(f"  {offset}/{pair_count} processed, {total_inserted} inserted...")

        conn.commit()
        print(f"Inserted: {total_inserted}, missed: {total_missed}")

        # Step 5: Verify
        final_count = conn.execute("SELECT COUNT(*) FROM school_majors").fetchone()[0]
        schools_covered = conn.execute(
            "SELECT COUNT(DISTINCT school_id) FROM school_majors"
        ).fetchone()[0]
        total_schools = conn.execute("SELECT COUNT(*) FROM schools").fetchone()[0]

        print(f"Final school_majors rows: {final_count}")
        print(f"Schools with majors: {schools_covered} / {total_schools}")

        # Sample
        samples = conn.execute("""
            SELECT sm.id, s.name, m.name, sm.year
            FROM school_majors sm
            JOIN schools s ON s.id = sm.school_id
            JOIN majors m ON m.id = sm.major_id
            LIMIT 5
        """).fetchall()
        for row in samples:
            print(f"  [{row[0]}] {row[1]} — {row[2]} (year={row[3]})")

        # Cleanup
        conn.execute("DROP TABLE IF EXISTS _tmp_sm")
        conn.commit()
        print("\nStage 1 complete!")

    except Exception as e:
        conn.rollback()
        print(f"ERROR: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    populate()
