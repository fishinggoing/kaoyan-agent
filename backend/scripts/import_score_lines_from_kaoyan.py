"""
Import kaoyan.cn school score lines into score_lines table.

STRICT FILTER: only imports (school_id, major_code) pairs that EXIST in school_majors.
Uses chunked JSON loading and frequent commits to avoid OOM.

Usage: cd backend && PYTHONPATH=. python scripts/import_score_lines_from_kaoyan.py [--dry-run]
"""
import json
import sys
from pathlib import Path
from difflib import SequenceMatcher
from collections import defaultdict

from sqlalchemy import text
from app.db.database import engine

INPUT_PATH = Path(__file__).resolve().parent.parent.parent / "crawler_data" / "kaoyan_cn" / "school_scores_raw.json"
BATCH_SIZE = 2000


def build_school_map() -> dict[int, int]:
    """Map kaoyan.cn school_id -> DB school_id via fuzzy name matching."""
    schools_path = INPUT_PATH.parent / "schools_raw.json"
    with open(schools_path, encoding="utf-8") as f:
        kaoyan_schools = json.load(f)["schools"]

    with engine.connect() as conn:
        db_schools = {r[1]: r[0] for r in conn.execute(text(
            "SELECT id, name FROM schools"
        )).fetchall()}

    mapping: dict[int, int] = {}
    unmatched: list[tuple[int, str, float]] = []

    for ks in kaoyan_schools:
        kname = ks["school_name"]
        kid = ks["school_id"]

        if kname in db_schools:
            mapping[kid] = db_schools[kname]
            continue

        best_score, best_id = 0.0, None
        for dbname, dbid in db_schools.items():
            ratio = SequenceMatcher(None, kname, dbname).ratio()
            if ratio > best_score:
                best_score, best_id = ratio, dbid

        if best_score >= 0.8 and best_id is not None:
            mapping[kid] = best_id
        else:
            unmatched.append((kid, kname, best_score))

    if unmatched:
        print(f"Unmatched kaoyan.cn schools: {len(unmatched)}")
        for kid, kname, score in sorted(unmatched, key=lambda x: x[2], reverse=True)[:10]:
            print(f"  {kid}: {kname} (best={score:.2f})")

    return mapping


def load_db_pairs() -> set[tuple[int, str]]:
    """Load all valid (school_id, major_code) pairs from school_majors.

    THIS IS THE KEY FILTER: only pairs where the school ACTUALLY offers this major.
    """
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT sm.school_id, m.code FROM school_majors sm
            JOIN majors m ON sm.major_id = m.id
            WHERE m.code IS NOT NULL AND LENGTH(m.code) = 6
        """)).fetchall()
    return {(r[0], r[1]) for r in rows}


def degree_type_to_category(dt: int | None) -> str:
    return "专硕" if dt == 1 else "学硕"


def insert_batch(conn, batch: list[dict]):
    for item in batch:
        conn.execute(text("""
            INSERT INTO score_lines
            (school_id, major_code, year, category, total_score,
             politics_score, english_score, business_score_1, business_score_2,
             is_national_line)
            VALUES
            (:school_id, :major_code, :year, :category, :total_score,
             :politics_score, :english_score, :business_score_1, :business_score_2,
             0)
        """), item)


def main():
    dry_run = "--dry-run" in sys.argv

    # === Step 1: Build lookup structures (small, in-memory) ===
    print("=== Step 1: Build school mapping ===")
    school_map = build_school_map()
    print(f"Mapped: {len(school_map)} kaoyan.cn ids -> DB school ids")

    print("\n=== Step 2: Load DB valid (school_id, major_code) pairs ===")
    db_pairs = load_db_pairs()
    print(f"Valid pairs in school_majors: {len(db_pairs)}")
    # Show a few examples
    sample = list(db_pairs)[:5]
    print(f"  Example pairs: {sample}")

    # === Step 2: Stream-process the big JSON ===
    print("\n=== Step 3: Stream-filter crawled records ===")
    print(f"Loading {INPUT_PATH} ...")
    with open(INPUT_PATH, encoding="utf-8") as f:
        raw = json.load(f)
    all_records = raw["records"]
    print(f"Total crawled records: {len(all_records)}")

    seen_keys: set[tuple[int, str, int]] = set()
    insert_batch_list: list[dict] = []
    stats = {
        "matched": 0,
        "no_school_mapping": 0,
        "no_pair_in_db": 0,
        "duplicate": 0,
        "inserted": 0,
    }

    # Process only school_score (6-digit) for precision
    for r in all_records:
        if r.get("data_type") != "school_score":
            continue

        db_sid = school_map.get(r["school_id"])
        if db_sid is None:
            stats["no_school_mapping"] += 1
            continue

        code = r.get("code", "")
        if (db_sid, code) not in db_pairs:
            stats["no_pair_in_db"] += 1
            continue

        year = int(r["year"])
        key = (db_sid, code, year)
        if key in seen_keys:
            stats["duplicate"] += 1
            continue
        seen_keys.add(key)

        stats["matched"] += 1
        politics = r.get("politics")
        english = r.get("english")
        spec1 = r.get("special_one")
        spec2 = r.get("special_two")

        insert_batch_list.append({
            "school_id": db_sid,
            "major_code": code,
            "year": year,
            "category": degree_type_to_category(r.get("degree_type")),
            "total_score": r["total"],
            "politics_score": politics if politics and politics != 0 else None,
            "english_score": english if english and english != 0 else None,
            "business_score_1": spec1 if spec1 and spec1 != 0 else None,
            "business_score_2": spec2 if spec2 and spec2 != 0 else None,
        })

        # Commit in batches to avoid OOM
        if len(insert_batch_list) >= BATCH_SIZE:
            if not dry_run:
                with engine.begin() as conn:
                    insert_batch(conn, insert_batch_list)
            stats["inserted"] += len(insert_batch_list)
            print(f"  Inserted {stats['inserted']}/{stats['matched']} ...")
            insert_batch_list = []

    # Final batch
    if insert_batch_list:
        if not dry_run:
            with engine.begin() as conn:
                insert_batch(conn, insert_batch_list)
        stats["inserted"] += len(insert_batch_list)

    print(f"\nStats:")
    print(f"  Matched (school+major pair exists in DB): {stats['matched']}")
    print(f"  No school mapping: {stats['no_school_mapping']}")
    print(f"  School+major pair NOT in DB (CORRECTLY SKIPPED): {stats['no_pair_in_db']}")
    print(f"  Duplicates skipped: {stats['duplicate']}")
    print(f"  Total inserted: {stats['inserted']}")

    # Year distribution
    by_year = defaultdict(int)
    for r in insert_batch_list:
        by_year[r["year"]] += 1
    print(f"By year: {dict(sorted(by_year.items()))}")

    covered_schools = len(set(r["school_id"] for r in insert_batch_list))
    covered_codes = len(set(r["major_code"] for r in insert_batch_list))
    print(f"Coverage: {covered_schools} schools, {covered_codes} major codes")

    if dry_run:
        print("\n=== DRY RUN — no changes made ===")
        return

    # === Step 4: Verify ===
    print("\n=== Step 4: Verify ===")
    with engine.connect() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM score_lines")).scalar()
        print(f"Total score_lines in DB: {count}")

        by_year_sql = conn.execute(text(
            "SELECT year, COUNT(*) FROM score_lines WHERE is_national_line = 0 "
            "GROUP BY year ORDER BY year"
        )).fetchall()
        print(f"By year: {[(r[0], r[1]) for r in by_year_sql]}")

        school_count = conn.execute(text(
            "SELECT COUNT(DISTINCT school_id) FROM score_lines WHERE is_national_line = 0"
        )).scalar()
        print(f"Distinct schools: {school_count}")

        # Verify: no orphan records (all (school_id, major_code) must exist in school_majors)
        orphan_count = conn.execute(text("""
            SELECT COUNT(*) FROM score_lines sl
            WHERE sl.is_national_line = 0
            AND NOT EXISTS (
                SELECT 1 FROM school_majors sm
                JOIN majors m ON sm.major_id = m.id
                WHERE sm.school_id = sl.school_id AND m.code = sl.major_code
            )
        """)).scalar()
        print(f"Orphan records (score_line without matching school_major): {orphan_count}")

        # Sample
        samples = conn.execute(text(
            "SELECT sl.school_id, s.name, sl.major_code, sl.year, sl.total_score "
            "FROM score_lines sl JOIN schools s ON sl.school_id = s.id "
            "WHERE sl.is_national_line = 0 LIMIT 10"
        )).fetchall()
        print("Sample records:")
        for r in samples:
            print(f"  {r[1]} | {r[2]} | {r[3]} | {r[4]}分")

    print("\nDone!")


if __name__ == "__main__":
    main()
