"""Reclassify all schools: add category column, fix level assignments.

Usage: python -m scripts.reclassify_schools
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text
from app.db.database import SessionLocal, engine
from app.models import School, SchoolLevel, SchoolCategory
from app.data.school_levels import classify_level, classify_category

LEVEL_MAP = {
    "C9": SchoolLevel.C9,
    "NINE_EIGHT_FIVE": SchoolLevel.NINE_EIGHT_FIVE,
    "TWO_ONE_ONE": SchoolLevel.TWO_ONE_ONE,
    "DOUBLE_FIRST_CLASS": SchoolLevel.DOUBLE_FIRST_CLASS,
    "REGULAR": SchoolLevel.REGULAR,
}

CATEGORY_MAP = {
    "ADULT_EDU": SchoolCategory.ADULT_EDU,
    "ASSOCIATE_UPGRADE": SchoolCategory.ASSOCIATE_UPGRADE,
    "GRAD_EXAM": SchoolCategory.GRAD_EXAM,
}


def run():
    db = SessionLocal()
    try:
        # Add category column if not exists
        col_exists = db.execute(text(
            "SELECT COUNT(*) FROM pragma_table_info('schools') WHERE name='category'"
        )).scalar()
        if not col_exists:
            db.execute(text("ALTER TABLE schools ADD COLUMN category VARCHAR(20)"))
            db.commit()
            print("Added 'category' column to schools table")

        schools = db.execute(
            text("SELECT id, name FROM schools")
        ).fetchall()

        # Extract 5-digit university codes for classification
        # We need the code from yantu data — try to match from known codes
        # For schools already in DB, we don't have the raw code. Use the
        # name-based classification first, then try to find level from existing
        # C9/985/211/双一流 labels, and default to 普本 for everything else.
        stats: dict[str, int] = {}
        updates = 0

        for school_id, name in schools:
            # Determine category by name
            cat_str = classify_category(name)
            cat_enum = CATEGORY_MAP[cat_str]

            if cat_str == "GRAD_EXAM":
                # For 考研 schools: keep existing level if it's C9/985/211/双一流,
                # otherwise default to 普本
                current_level_row = db.execute(
                    text("SELECT level FROM schools WHERE id = :sid"),
                    {"sid": school_id}
                ).scalar()
                # Keep existing high-tier classifications, fix the rest
                high_tiers = {"C9", "985", "211", "双一流"}
                if current_level_row in high_tiers:
                    level_str = current_level_row
                else:
                    level_str = "普本"
            else:
                # Non-考研 schools: use category as level label
                level_str = "普本"

            level_enum = LEVEL_MAP.get(level_str, SchoolLevel.REGULAR)

            db.execute(
                text("UPDATE schools SET level = :lev, category = :cat WHERE id = :sid"),
                {"lev": level_enum.value, "cat": cat_enum.value, "sid": school_id}
            )
            updates += 1

            key = f"{cat_str}|{level_str}"
            stats[key] = stats.get(key, 0) + 1

        db.commit()

        print(f"\n=== Reclassification complete: {updates} schools ===\n")
        for (cat, lev), cnt in sorted(stats.items(), key=lambda x: -x[1]):
            print(f"  {cat:12s} | {lev:6s} : {cnt:5d}")

        # Verify no 省属重点 or 普通 remains
        old = db.execute(
            text("SELECT COUNT(*) FROM schools WHERE level IN ('省属重点', '普通')")
        ).scalar()
        print(f"\nOld levels remaining: {old} (should be 0)")

    except Exception as e:
        db.rollback()
        print(f"Migration failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run()
