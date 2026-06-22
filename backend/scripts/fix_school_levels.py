"""
Fix school levels in the database using the corrected classify_level().

Usage: python -m scripts.fix_school_levels
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.database import SessionLocal
from app.models import School, SchoolLevel, SchoolCategory
from app.data.school_levels import classify_level, classify_category
from sqlalchemy import select

YANTU_DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "yantu_schools.json"

LEVEL_MAP = {
    "C9": SchoolLevel.C9,
    "NINE_EIGHT_FIVE": SchoolLevel.NINE_EIGHT_FIVE,
    "TWO_ONE_ONE": SchoolLevel.TWO_ONE_ONE,
    "DOUBLE_FIRST_CLASS": SchoolLevel.DOUBLE_FIRST_CLASS,
    "REGULAR": SchoolLevel.REGULAR,
}


def extract_univ_code(yantu_code: str) -> str:
    if len(yantu_code) >= 10:
        return yantu_code[5:10]
    return yantu_code


def build_name_to_code() -> dict[str, str]:
    """Build a mapping of school name → 5-digit code from yantu data."""
    if not YANTU_DATA_FILE.exists():
        print(f"Warning: {YANTU_DATA_FILE} not found, using name-based fallback")
        return {}

    with open(YANTU_DATA_FILE, "r", encoding="utf-8") as f:
        raw = json.load(f)

    schools_data = raw.get("data", raw if isinstance(raw, list) else [])
    mapping: dict[str, str] = {}
    for item in schools_data:
        name = item.get("name", "").strip()
        yantu_code = item.get("code", "").strip()
        if name and yantu_code:
            code = extract_univ_code(yantu_code)
            mapping[name] = code
    print(f"Built name→code mapping: {len(mapping)} entries")
    return mapping


def fix_school_levels():
    db = SessionLocal()

    try:
        name_to_code = build_name_to_code()
        schools = db.execute(select(School)).scalars().all()
        print(f"Found {len(schools)} schools in DB")

        level_counts_before = {}
        level_counts_after = {}
        changes = []

        for school in schools:
            old_level = school.level.value if school.level else "unknown"
            level_counts_before[old_level] = level_counts_before.get(old_level, 0) + 1

            code = name_to_code.get(school.name, "")
            new_level_str = classify_level(code, school.name)
            new_level = LEVEL_MAP.get(new_level_str, SchoolLevel.REGULAR)

            cat_str = classify_category(school.name)
            cat_map = {
                "ADULT_EDU": SchoolCategory.ADULT_EDU,
                "ASSOCIATE_UPGRADE": SchoolCategory.ASSOCIATE_UPGRADE,
                "GRAD_EXAM": SchoolCategory.GRAD_EXAM,
            }
            new_category = cat_map.get(cat_str, SchoolCategory.GRAD_EXAM)

            if school.level != new_level:
                changes.append(
                    f"  {school.name} ({school.province}): {old_level} → {new_level_str}"
                )
                school.level = new_level
            school.category = new_category

            level_counts_after[new_level_str] = level_counts_after.get(new_level_str, 0) + 1

        db.commit()

        print(f"\n=== Level Distribution Before ===")
        for k, v in sorted(level_counts_before.items(), key=lambda x: -x[1]):
            print(f"  {k}: {v}")
        print(f"\n=== Level Distribution After ===")
        for k, v in sorted(level_counts_after.items(), key=lambda x: -x[1]):
            print(f"  {k}: {v}")
        print(f"\n=== Changes: {len(changes)} ===")
        for c in changes:
            print(c)

    except Exception as e:
        db.rollback()
        print(f"Migration failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    fix_school_levels()
