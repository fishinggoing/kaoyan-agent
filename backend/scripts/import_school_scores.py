"""
Import kaoyan.cn school-specific score lines into score_lines table.

Maps kaoyan.cn school_id → DB school_id via fuzzy name matching.
Handles both data_type="score_level" (broad category) and "school_score" (specific major).

Usage: cd backend && PYTHONPATH=. python scripts/import_school_scores.py
"""
import json
import sys
from pathlib import Path
from difflib import SequenceMatcher

from sqlalchemy import text
from app.db.database import engine

INPUT_PATH = Path(__file__).resolve().parent.parent.parent / "crawler_data" / "kaoyan_cn" / "school_scores_raw.json"


def load_raw_data() -> tuple[list[dict], dict]:
    with open(INPUT_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return data["records"], data.get("stats", {})


def build_school_map() -> dict[int, int]:
    """Map kaoyan.cn school_id → DB school_id by name matching."""
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT id, name FROM schools WHERE category = 'GRAD_EXAM'")).fetchall()

    db_schools = {r[1]: r[0] for r in rows}

    # Load kaoyan.cn school names
    schools_path = INPUT_PATH.parent / "schools_raw.json"
    with open(schools_path, encoding="utf-8") as f:
        kaoyan_schools = json.load(f)["schools"]

    mapping: dict[int, int] = {}
    unmatched = []

    for ks in kaoyan_schools:
        kname = ks["school_name"]
        kid = ks["school_id"]

        # Try exact match first
        if kname in db_schools:
            mapping[kid] = db_schools[kname]
            continue

        # Fuzzy match
        best_score = 0.0
        best_id = None
        for dbname, dbid in db_schools.items():
            ratio = SequenceMatcher(None, kname, dbname).ratio()
            if ratio > best_score:
                best_score = ratio
                best_id = dbid

        if best_score >= 0.8 and best_id is not None:
            mapping[kid] = best_id
        else:
            unmatched.append((kid, kname))

    if unmatched:
        print(f"Warning: {len(unmatched)} schools unmatched (kaoyan_id → name):")
        for kid, kname in unmatched[:20]:
            print(f"  {kid}: {kname}")

    return mapping


def import_records(dry_run: bool = False):
    records, stats = load_raw_data()
    print(f"Loaded {len(records)} records from {INPUT_PATH}")
    print(f"Stats: {stats}")

    school_map = build_school_map()
    print(f"School mapping: {len(school_map)} kaoyan.cn ids → DB ids")

    # Analyze records
    by_type = {}
    by_year = {}
    for r in records:
        by_type[r.get("data_type", "?")] = by_type.get(r.get("data_type", "?"), 0) + 1
        by_year[r.get("year", "?")] = by_year.get(r.get("year", "?"), 0) + 1
    print(f"By data_type: {by_type}")
    print(f"By year: {by_year}")

    # Count how many can be matched
    matched = sum(1 for r in records if r["school_id"] in school_map)
    unmatched = len(records) - matched
    print(f"Matched: {matched}, Unmatched: {unmatched}")

    if dry_run:
        print("DRY RUN - no changes made")
        return

    # Deduplicate: same (school_id, major_code, year) → keep first
    seen = set()
    deduped: list[dict] = []
    dupes = 0
    for r in records:
        kaoyan_sid = r["school_id"]
        db_sid = school_map.get(kaoyan_sid)
        if db_sid is None:
            continue
        key = (db_sid, r["code"], int(r["year"]))
        if key in seen:
            dupes += 1
            continue
        seen.add(key)
        deduped.append(r)
    print(f"Dedup: removed {dupes} duplicate keys, {len(deduped)} unique remaining")

    with engine.begin() as conn:
        # Delete existing synthetic scores for schools we'll replace
        # Only delete for matched schools to preserve data for unmatched ones
        matched_db_ids = set(school_map.values())
        batch_size = 500
        id_list = list(matched_db_ids)
        for i in range(0, len(id_list), batch_size):
            batch = id_list[i:i + batch_size]
            placeholders = ",".join(str(x) for x in batch)
            conn.execute(text(f"""
                DELETE FROM score_lines
                WHERE is_national_line = 0
                AND year IN (2022, 2023, 2024, 2025, 2026)
                AND school_id IN ({placeholders})
            """))
        print(f"Cleared old scores for {len(matched_db_ids)} matched schools")

        inserted = 0
        for r in deduped:
            db_sid = school_map[r["school_id"]]

            politics = r.get("politics")
            english = r.get("english")
            special_one = r.get("special_one")
            special_two = r.get("special_two")

            conn.execute(text("""
                INSERT INTO score_lines
                (school_id, major_code, year, category, total_score,
                 politics_score, english_score, business_score_1, business_score_2,
                 is_national_line)
                VALUES
                (:school_id, :major_code, :year, :category, :total_score,
                 :politics, :english, :business_1, :business_2, 0)
            """), {
                "school_id": db_sid,
                "major_code": r["code"],
                "year": int(r["year"]),
                "category": "A",
                "total_score": r["total"],
                "politics": politics if politics and politics != 0 else None,
                "english": english if english and english != 0 else None,
                "business_1": special_one if special_one and special_one != 0 else None,
                "business_2": special_two if special_two and special_two != 0 else None,
            })
            inserted += 1

        print(f"Inserted: {inserted}")

    # Verify
    with engine.connect() as conn:
        count = conn.execute(text(
            "SELECT COUNT(*) FROM score_lines WHERE is_national_line = 0 AND year IN ('2022','2023','2024','2025','2026')"
        )).scalar()
        print(f"Total school-specific lines in DB after import: {count}")


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    import_records(dry_run=dry_run)
