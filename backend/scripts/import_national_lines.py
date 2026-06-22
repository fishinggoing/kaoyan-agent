"""
Import real national line data from kaoyan.cn crawl into the database.

Replaces synthetic national lines with real data for 2022-2026 across all
discipline categories.

Two-pass: 2-digit lines first, then 4-digit overrides for sub-disciplines
(照顾专业 etc.) that have different score thresholds.

Data source: POST api.kaoyan.cn/pc/school/specialScoreGj

Usage: cd backend && PYTHONPATH=. python scripts/import_national_lines.py
"""
import json
import sys
from pathlib import Path

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.database import SessionLocal

CRAWLED_DATA = (
    Path(__file__).resolve().parent.parent.parent
    / "crawler_data" / "kaoyan_cn" / "national_lines_all.json"
)

DEGREE_MAP = {1: "专硕", 2: "学硕"}
PLACEHOLDER_SCHOOL_ID = 999999


def load_crawled_data() -> list[dict]:
    with open(CRAWLED_DATA, "r", encoding="utf-8") as f:
        return json.load(f)["records"]


def main():
    db = SessionLocal()
    records = load_crawled_data()
    print(f"Loaded {len(records)} national line records")

    all_codes = {
        r[0]
        for r in db.execute(
            text("SELECT DISTINCT code FROM majors WHERE code IS NOT NULL")
        ).fetchall()
    }
    print(f"Found {len(all_codes)} distinct major codes in DB")

    # Clear old national lines
    old_count = db.execute(
        text("SELECT COUNT(*) FROM score_lines WHERE is_national_line = 1")
    ).scalar()
    db.execute(text("DELETE FROM score_lines WHERE is_national_line = 1"))
    print(f"Cleared {old_count} old synthetic national lines")

    # Process shorter prefixes first so 4-digit lines override 2-digit ones
    sorted_records = sorted(records, key=lambda r: len(r["code"]))

    inserted = 0
    for i, rec in enumerate(sorted_records):
        # Only import A类 (A区) national lines — covers most provinces
        if rec["area_type"] != "A":
            continue
        prefix = rec["code"]
        year = rec["year"]
        category = DEGREE_MAP.get(rec["degree_type"], "学硕")
        total = rec["total"]
        s100 = rec["single_100"]
        s150 = rec["single_150"]

        matching = [c for c in all_codes if c.startswith(prefix)]
        if not matching:
            continue

        # Delete existing national line entries for this (prefix, year, category)
        db.execute(
            text(
                "DELETE FROM score_lines WHERE is_national_line = 1 "
                "AND major_code LIKE :like AND year = :year AND category = :cat"
            ),
            {"like": f"{prefix}%", "year": year, "cat": category},
        )

        # Batch insert all matching codes
        for mcode in matching:
            db.execute(
                text(
                    "INSERT INTO score_lines "
                    "(school_id, major_code, year, category, total_score, "
                    "politics_score, english_score, business_score_1, business_score_2, "
                    "is_national_line) "
                    "VALUES (:sid, :code, :year, :cat, :ts, :ps, :es, :b1, :b2, 1)"
                ),
                {
                    "sid": PLACEHOLDER_SCHOOL_ID,
                    "code": mcode, "year": year, "cat": category,
                    "ts": total, "ps": s100, "es": s100,
                    "b1": s150, "b2": s150,
                },
            )
            inserted += 1

        if i % 50 == 49:
            db.commit()
            print(f"  ... {i + 1}/{len(sorted_records)} records, {inserted} rows")

    db.commit()
    print(f"\nInserted {inserted} national line rows")

    # Verify
    count = db.execute(
        text("SELECT COUNT(*) FROM score_lines WHERE is_national_line = 1")
    ).scalar()
    print(f"Total national lines: {count}")

    # Sample: general engineering vs 照顾专业
    for label, prefix in [("普通工学", "0812%"), ("力学(照顾)", "0801%")]:
        samples = db.execute(
            text(
                "SELECT year, major_code, total_score "
                "FROM score_lines WHERE is_national_line = 1 "
                f"AND major_code LIKE :pfx AND year = 2022 LIMIT 2"
            ),
            {"pfx": prefix},
        ).fetchall()
        print(f"  {label} 2022: {[(s[0], s[1], s[2]) for s in samples]}")

    db.close()


if __name__ == "__main__":
    main()
