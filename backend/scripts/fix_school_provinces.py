"""
Fix school provinces using yantu code (positions 2-3 = GB province code).

Usage: python -m scripts.fix_school_provinces
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.database import SessionLocal
from app.models import School
from app.data.province_mapping import get_province, get_city

YANTU_DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "yantu_schools.json"


def extract_univ_code(yantu_code: str) -> str:
    if len(yantu_code) >= 10:
        return yantu_code[5:10]
    return yantu_code


def build_name_to_yantu_code() -> dict[str, str]:
    """Build school name → full 10-digit yantu code mapping."""
    if not YANTU_DATA_FILE.exists():
        print("Warning: {} not found".format(YANTU_DATA_FILE))
        return {}

    with open(YANTU_DATA_FILE, "r", encoding="utf-8") as f:
        raw = json.load(f)

    schools_data = raw.get("data", raw if isinstance(raw, list) else [])
    mapping: dict[str, str] = {}
    for item in schools_data:
        name = item.get("name", "").strip()
        yantu_code = item.get("code", "").strip()
        if name and yantu_code:
            mapping[name] = yantu_code
    print("Built name to yantu_code mapping: {} entries".format(len(mapping)))
    return mapping


def fix_school_provinces():
    db = SessionLocal()

    try:
        name_to_yantu = build_name_to_yantu_code()
        schools = db.query(School).all()
        print("Found {} schools in DB".format(len(schools)))

        province_counts_before = {}
        province_counts_after = {}
        changes = []

        for school in schools:
            old_province = school.province or "unknown"
            province_counts_before[old_province] = province_counts_before.get(old_province, 0) + 1

            yantu_code = name_to_yantu.get(school.name, "")
            univ_code = extract_univ_code(yantu_code) if yantu_code else ""

            new_province = get_province(
                univ_code=univ_code,
                school_name=school.name,
                yantu_code=yantu_code,
            )

            if school.province != new_province:
                changes.append(
                    "  {} ({} -> {})".format(school.name, old_province, new_province)
                )
                school.province = new_province
                school.city = get_city(new_province)

            province_counts_after[new_province] = province_counts_after.get(new_province, 0) + 1

        db.commit()

        print("\n=== Province Distribution Before ===")
        for k, v in sorted(province_counts_before.items(), key=lambda x: -x[1]):
            print("  {}: {}".format(k, v))
        print("\n=== Province Distribution After ===")
        for k, v in sorted(province_counts_after.items(), key=lambda x: -x[1]):
            print("  {}: {}".format(k, v))
        print("\n=== Changes: {} ===".format(len(changes)))
        for c in changes:
            print(c)

    except Exception as e:
        db.rollback()
        print("Migration failed: {}".format(e))
        raise
    finally:
        db.close()


if __name__ == "__main__":
    fix_school_provinces()
