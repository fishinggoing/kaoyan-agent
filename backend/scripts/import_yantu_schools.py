"""
Import 14,763 schools from 研途 (yantu.com.cn) API into the database.

Usage: python -m scripts.import_yantu_schools
"""
import json
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.database import SessionLocal, engine, Base
from app.models import School, SchoolLevel, SchoolType, SchoolCategory
from app.data.province_mapping import get_province, get_city
from app.data.school_levels import classify_level, classify_category

YANTU_DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "yantu_schools.json"

# School type inference from name keywords
NAME_TYPE_HINTS = [
    ("师范", SchoolType.NORMAL),
    ("财经", SchoolType.FINANCE_ECONOMICS),
    ("农业", SchoolType.AGRICULTURE),
    ("医科", SchoolType.MEDICAL),
    ("医药", SchoolType.MEDICAL),
    ("中医药", SchoolType.MEDICAL),
    ("政法", SchoolType.LANGUAGE_LAW),
    ("外国语", SchoolType.LANGUAGE_LAW),
    ("美术", SchoolType.ART_SPORTS),
    ("音乐", SchoolType.ART_SPORTS),
    ("体育", SchoolType.ART_SPORTS),
    ("艺术", SchoolType.ART_SPORTS),
    ("理工", SchoolType.SCIENCE_ENGINEERING),
    ("科技", SchoolType.SCIENCE_ENGINEERING),
    ("工业", SchoolType.SCIENCE_ENGINEERING),
    ("林业", SchoolType.AGRICULTURE),
    ("海洋", SchoolType.SCIENCE_ENGINEERING),
]


def infer_school_type(name: str) -> SchoolType:
    """Guess school type from name keywords."""
    for keyword, stype in NAME_TYPE_HINTS:
        if keyword in name:
            return stype
    return SchoolType.COMPREHENSIVE


def extract_univ_code(yantu_code: str) -> str:
    """Extract the 5-digit standard university code from yantu's 10-digit code."""
    if len(yantu_code) >= 10:
        return yantu_code[5:10]
    return yantu_code


def import_schools():
    if not YANTU_DATA_FILE.exists():
        print(f"Data file not found: {YANTU_DATA_FILE}")
        print("Please save yantu /api/school response to data/yantu_schools.json first.")
        sys.exit(1)

    with open(YANTU_DATA_FILE, "r", encoding="utf-8") as f:
        raw = json.load(f)

    schools_data = raw.get("data", raw if isinstance(raw, list) else [])
    print(f"Loaded {len(schools_data)} schools from {YANTU_DATA_FILE}")

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        existing = db.query(School).count()
        if existing > 100:
            print(f"Database already has {existing} schools. Skipping import.")
            return

        imported = 0
        skipped = 0
        seen = set()
        level_counts = {}

        for item in schools_data:
            name = item.get("name", "").strip()
            yantu_code = item.get("code", "").strip()
            univ_code = extract_univ_code(yantu_code)

            if not name or not univ_code:
                skipped += 1
                continue

            dedup_key = (name, univ_code)
            if dedup_key in seen:
                skipped += 1
                continue
            seen.add(dedup_key)

            province = get_province(univ_code, name, yantu_code)
            city = get_city(province)
            level_str = classify_level(univ_code, name)
            cat_str = classify_category(name)
            school_type = infer_school_type(name)

            # Map level string to enum
            level_map = {
                "C9": SchoolLevel.C9,
                "NINE_EIGHT_FIVE": SchoolLevel.NINE_EIGHT_FIVE,
                "TWO_ONE_ONE": SchoolLevel.TWO_ONE_ONE,
                "DOUBLE_FIRST_CLASS": SchoolLevel.DOUBLE_FIRST_CLASS,
                "REGULAR": SchoolLevel.REGULAR,
            }
            cat_map = {
                "ADULT_EDU": SchoolCategory.ADULT_EDU,
                "ASSOCIATE_UPGRADE": SchoolCategory.ASSOCIATE_UPGRADE,
                "GRAD_EXAM": SchoolCategory.GRAD_EXAM,
            }
            level = level_map.get(level_str, SchoolLevel.REGULAR)
            category = cat_map.get(cat_str, SchoolCategory.GRAD_EXAM)
            level_counts[level_str] = level_counts.get(level_str, 0) + 1

            db.add(School(
                name=name,
                province=province,
                city=city,
                level=level,
                category=category,
                school_type=school_type,
                is_graduate_school=("研究生" in name or "研究院" in name or "研究所" in name or "科学院" in name),
                description=None,
                ranking_national=None,
            ))
            imported += 1

            if imported % 2000 == 0:
                db.commit()
                print(f"  {imported}/{len(schools_data)} imported...")

        db.commit()

        print(f"\n=== Import complete ===")
        print(f"Imported: {imported}")
        print(f"Skipped: {skipped}")
        print(f"Level distribution: {level_counts}")
        print(f"Total in DB: {db.query(School).count()}")

    except Exception as e:
        db.rollback()
        print(f"Import failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    import_schools()
