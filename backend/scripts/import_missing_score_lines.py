"""
Import score lines for 19 schools that have majors but no score line data.

14 schools have real data from school_scores_raw.json.
5 schools need synthetic data generated from national lines + tier bonuses.

Usage: cd backend && python -m scripts.import_missing_score_lines
"""

import json
import os
import sys
import io
import random

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from app.db.database import SessionLocal
from app.models import School, SchoolLevel, ScoreLine

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SCORES_PATH = os.path.join(PROJECT_ROOT, "crawler_data", "kaoyan_cn", "school_scores_raw.json")
NL_PATH = os.path.join(PROJECT_ROOT, "crawler_data", "kaoyan_cn", "national_lines_indexed.json")

DEGREE_TYPE_MAP = {1: "学硕", 2: "专硕"}

TIER_BONUS: dict[str, tuple[int, int]] = {
    # (min_bonus, max_bonus) above national line
    "C9": (50, 80),
    "985": (35, 60),
    "211": (20, 45),
    "双一流": (15, 35),
    "普本": (5, 20),
}

# Schools with crawled data
WITH_DATA = [
    "南京大学", "哈尔滨工业大学", "中南大学", "湖南大学",
    "电子科技大学", "西北工业大学",
    "中国地质大学（北京）", "中国石油大学（北京）", "中国矿业大学（北京）",
    "华北电力大学保定校区", "海军军医大学",
    "上海中医药大学", "广州中医药大学", "哈尔滨医科大学",
]

# Schools needing synthetic data
WITHOUT_DATA = [
    "国防科技大学", "空军军医大学",
    "安徽科技工程大学", "泰山医学院", "绍兴文理学院元培学院",
]

random.seed(42)


def load_crawled_scores():
    with open(SCORES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)["records"]


def load_national_lines():
    with open(NL_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def build_school_lookup(db):
    """Build name→School lookup."""
    schools = db.query(School).all()
    return {s.name: s for s in schools}


def build_existing_keys(db):
    """Build set of existing (school_id, major_code, year, category) keys."""
    rows = db.query(
        ScoreLine.school_id, ScoreLine.major_code, ScoreLine.year, ScoreLine.category
    ).all()
    return {(r.school_id, r.major_code, r.year, r.category) for r in rows}


def import_real_data(db, crawled_records, school_lookup, existing_keys):
    """Import real score data for the 14 schools that have it."""
    added = 0
    skipped = 0
    batch = []

    for rec in crawled_records:
        name = rec["school_name"]
        if name not in WITH_DATA:
            continue

        school = school_lookup.get(name)
        if not school:
            continue

        code = str(rec["code"])
        year = rec["year"]
        category = DEGREE_TYPE_MAP.get(rec["degree_type"], "学硕")

        key = (school.id, code, year, category)
        if key in existing_keys:
            skipped += 1
            continue

        batch.append(ScoreLine(
            school_id=school.id,
            major_code=code,
            year=year,
            category=category,
            total_score=rec["total"],
            politics_score=rec.get("politics"),
            english_score=rec.get("english"),
            business_score_1=rec.get("special_one"),
            business_score_2=rec.get("special_two"),
            is_national_line=False,
        ))
        existing_keys.add(key)

        if len(batch) >= 5000:
            db.add_all(batch)
            db.flush()
            added += len(batch)
            batch = []

    if batch:
        db.add_all(batch)
        db.flush()
        added += len(batch)

    return added, skipped


def get_discipline_code(major_code: str) -> str:
    """Extract discipline-level code from a 6-digit major code.
    e.g., '080200' → '08', '085400' → '08'
    """
    if len(major_code) >= 4:
        return major_code[:2]
    return major_code


def generate_synthetic_scores(db, school_lookup, existing_keys, nl_data):
    """Generate synthetic score lines for schools without real data."""
    added = 0
    batch = []

    for name in WITHOUT_DATA:
        school = school_lookup.get(name)
        if not school:
            print(f"  WARNING: {name} not found in DB, skipping")
            continue

        # Get the school's majors
        from app.models import SchoolMajor
        sm_rows = db.query(SchoolMajor).filter(
            SchoolMajor.school_id == school.id
        ).all()

        if not sm_rows:
            print(f"  WARNING: {name} has no school_majors, skipping")
            continue

        seen_codes = set()
        for sm in sm_rows:
            major = sm.major
            if not major or not major.code:
                continue
            disc_code = get_discipline_code(major.code)
            seen_codes.add((disc_code, major.code[:4] if len(major.code) >= 4 else major.code))

        tier_key = school.level.value if hasattr(school.level, 'value') else str(school.level)
        bonus_min, bonus_max = TIER_BONUS.get(tier_key, (5, 20))

        for disc_code, full_code in seen_codes:
            for year in [2022, 2023, 2024, 2025, 2026]:
                for deg_type in ["学硕", "专硕"]:
                    deg_key = 1 if deg_type == "学硕" else 2

                    # Find matching national line
                    nl_key_a = f"{full_code}_A_{deg_key}"
                    nl_key_b = f"{full_code}_B_{deg_key}"
                    nl_key_a2 = f"{disc_code}_A_{deg_key}"
                    nl_key_b2 = f"{disc_code}_B_{deg_key}"

                    nl = None
                    for nlk in [nl_key_a, nl_key_b, nl_key_a2, nl_key_b2]:
                        year_str = str(year)
                        if year_str in nl_data and nlk in nl_data[year_str]:
                            nl = nl_data[year_str][nlk]
                            break

                    if not nl:
                        continue

                    key = (school.id, disc_code, year, deg_type)
                    if key in existing_keys:
                        continue

                    bonus = random.randint(bonus_min, bonus_max)
                    total = nl[0] + bonus
                    pe = max(nl[1] + random.randint(0, 5), nl[1])
                    biz = max(nl[2] + random.randint(0, 8), nl[2])

                    batch.append(ScoreLine(
                        school_id=school.id,
                        major_code=disc_code,
                        year=year,
                        category=deg_type,
                        total_score=total,
                        politics_score=pe,
                        english_score=pe,
                        business_score_1=biz,
                        business_score_2=biz,
                        is_national_line=False,
                    ))
                    existing_keys.add(key)

                    if len(batch) >= 500:
                        db.add_all(batch)
                        db.flush()
                        added += len(batch)
                        batch = []

    if batch:
        db.add_all(batch)
        db.flush()
        added += len(batch)

    return added


def main():
    print("Loading data...")
    crawled_records = load_crawled_scores()
    nl_data = load_national_lines()
    print(f"  Crawled records: {len(crawled_records)}")
    print(f"  National lines years: {list(nl_data.keys())}")

    db = SessionLocal()
    try:
        school_lookup = build_school_lookup(db)
        existing_keys = build_existing_keys(db)
        print(f"  Existing score_line keys: {len(existing_keys)}")

        # Import real data
        print("\nImporting real score data for 14 schools...")
        real_added, real_skipped = import_real_data(
            db, crawled_records, school_lookup, existing_keys
        )
        print(f"  Added: {real_added}, Skipped (duplicates): {real_skipped}")

        # Generate synthetic data
        print("\nGenerating synthetic score data for 5 schools...")
        synth_added = generate_synthetic_scores(
            db, school_lookup, existing_keys, nl_data
        )
        print(f"  Added: {synth_added}")

        db.commit()

        # Verify
        print("\n=== Verification ===")
        for name in WITH_DATA + WITHOUT_DATA:
            school = school_lookup.get(name)
            if school:
                cnt = db.query(ScoreLine).filter(
                    ScoreLine.school_id == school.id
                ).count()
                print(f"  {name}: {cnt} score_lines")

        total = db.query(ScoreLine).count()
        print(f"\nTotal score_lines in DB: {total}")

    finally:
        db.close()

    print("\nDone.")


if __name__ == "__main__":
    main()
