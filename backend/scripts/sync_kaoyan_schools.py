"""
Sync DB schools with kaoyan.cn authoritative school list.

Actions:
1. Match kaoyan.cn schools to DB by exact name + known renames
2. Update renamed schools (e.g. 嘉兴学院 -> 嘉兴大学)
3. Insert truly new schools (with city='')
4. Set correct level (preserving C9) and category=GRAD_EXAM for matched schools
5. Report unmatched for manual review

Usage: cd backend && PYTHONPATH=. python scripts/sync_kaoyan_schools.py
"""
import json
import sys
from pathlib import Path
from difflib import SequenceMatcher

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.database import SessionLocal
from app.models import School, SchoolLevel, SchoolCategory, SchoolType
from app.data.school_levels import classify_level, classify_category, C9_NAMES
from app.data.province_mapping import get_province

KAOYAN_FILE = (
    Path(__file__).resolve().parent.parent.parent
    / "crawler_data" / "kaoyan_cn" / "schools_raw.json"
)

LEVEL_MAP = {
    "C9": SchoolLevel.C9,
    "NINE_EIGHT_FIVE": SchoolLevel.NINE_EIGHT_FIVE,
    "TWO_ONE_ONE": SchoolLevel.TWO_ONE_ONE,
    "DOUBLE_FIRST_CLASS": SchoolLevel.DOUBLE_FIRST_CLASS,
    "REGULAR": SchoolLevel.REGULAR,
}
CAT_MAP = {
    "ADULT_EDU": SchoolCategory.ADULT_EDU,
    "ASSOCIATE_UPGRADE": SchoolCategory.ASSOCIATE_UPGRADE,
    "GRAD_EXAM": SchoolCategory.GRAD_EXAM,
}

# kaoyan.cn new name -> DB old name (recently renamed universities)
KNOWN_RENAMES: dict[str, str] = {
    # 学院→大学 renames (confirmed)
    "佛山大学": "佛山科学技术学院",
    "嘉兴大学": "嘉兴学院",
    "福建理工大学": "福建工程学院",
    "桂林医科大学": "桂林医学院",
    "山东航空学院": "滨州学院",
    "蚌埠医科大学": "蚌埠医学院",
    "赤峰大学": "赤峰学院",
    "绍兴大学": "绍兴文理学院",
    "淮安大学": "淮阴工学院",
    "赣南医科大学": "赣南医学院",
    "合肥大学": "合肥学院",
    "浙江科技大学": "浙江科技学院",
    "山东第二医科大学": "潍坊医学院",
    "河北中医药大学": "河北中医学院",
    "重庆三峡科技大学": "重庆三峡学院",
    "江西水利电力大学": "南昌工程学院",
    "重庆科技大学": "重庆科技学院",
    "海南医科大学": "海南医学院",
    "皖南医科大学": "皖南医学院",
    "牡丹江医科大学": "牡丹江医学院",
    "山东医药大学": "山东第一医科大学",
    "河南医药大学": "新乡医学院",
    "湖州师范大学": "湖州师范学院",
    "信阳师范大学": "信阳师范学院",
    "天水师范大学": "天水师范学院",
    "宁夏师范大学": "宁夏师范学院",
    "吉林化工大学": "吉林化工学院",
    "湖南理工大学": "湖南理工学院",
    "安徽科技工程大学": "安徽科技学院",
    "西藏农牧大学": "西藏农牧学院",
    "苏州工学院": "常熟理工学院",
    "南京警察学院": "南京森林警察学院",
}

# Schools in kaoyan.cn that don't exist in DB at all (truly new)
# These get inserted
TRULY_NEW: set[str] = {
    "重庆中医药学院",
    "深圳理工大学",
}

# Sub-campuses: kaoyan.cn has separate entries but DB has one parent
SUB_CAMPUSES: dict[str, str] = {
    "内蒙古科技大学包头师范学院": "内蒙古科技大学",
    "内蒙古科技大学包头医学院": "内蒙古科技大学",
}


def match_schools():
    with open(KAOYAN_FILE, "r", encoding="utf-8") as f:
        kaoyan_schools = json.load(f)["schools"]

    db = SessionLocal()
    db_schools: dict[str, School] = {s.name: s for s in db.query(School).all()}
    db_names = list(db_schools.keys())

    print(f"kaoyan.cn: {len(kaoyan_schools)} schools")
    print(f"DB: {len(db_names)} schools")

    stats = {
        "exact_match": 0,
        "renamed": 0,
        "inserted": 0,
        "level_fixed": 0,
        "category_fixed": 0,
        "unmatched": 0,
    }
    unmatched: list[tuple[str, str, str]] = []  # (name, province, best_match)

    for s in kaoyan_schools:
        name = s["school_name"]
        school_id = s["school_id"]
        is_985 = s.get("is_985") == 1
        is_211 = s.get("is_211") == 1
        is_syl = s.get("syl") == 1
        province_name = s.get("province_name", "")

        # Determine target level — preserve C9
        if name in C9_NAMES:
            target_level = "C9"
        elif is_985:
            target_level = "NINE_EIGHT_FIVE"
        elif is_211:
            target_level = "TWO_ONE_ONE"
        elif is_syl:
            target_level = "DOUBLE_FIRST_CLASS"
        else:
            target_level = "REGULAR"

        # --- Find matching DB school ---
        db_school: School | None = None

        if name in db_schools:
            db_school = db_schools[name]
            stats["exact_match"] += 1
        elif name in KNOWN_RENAMES:
            old_name = KNOWN_RENAMES[name]
            if old_name in db_schools:
                db_school = db_schools[old_name]
                print(f"  RENAME: {old_name} -> {name}")
                db_school.name = name
                del db_schools[old_name]
                db_schools[name] = db_school
                stats["renamed"] += 1
        elif name in SUB_CAMPUSES:
            parent_name = SUB_CAMPUSES[name]
            if parent_name in db_schools:
                parent_s = db_schools[parent_name]
                prov = province_name if province_name else "未知"
                db.add(School(
                    name=name,
                    province=prov,
                    city=parent_s.city or "",
                    level=SchoolLevel.REGULAR,
                    category=SchoolCategory.GRAD_EXAM,
                    school_type=parent_s.school_type or SchoolType.COMPREHENSIVE,
                    is_graduate_school=True,
                ))
                stats["inserted"] += 1
                print(f"  INSERT (sub-campus): {name}")
                db.flush()
                continue

        # --- Update or insert ---
        if db_school:
            expected_level = LEVEL_MAP.get(target_level, SchoolLevel.REGULAR)
            if db_school.level != expected_level:
                old_lv = db_school.level.value if db_school.level else "NULL"
                db_school.level = expected_level
                stats["level_fixed"] += 1
                print(f"  FIX LEVEL: {name} {old_lv} -> {expected_level.value}")

            expected_cat = SchoolCategory.GRAD_EXAM
            if db_school.category != expected_cat:
                db_school.category = expected_cat
                stats["category_fixed"] += 1

            if not db_school.province and province_name:
                db_school.province = province_name
        else:
            # Truly new school - insert if confirmed
            if name in TRULY_NEW:
                prov = province_name if province_name else "未知"
                db.add(School(
                    name=name,
                    province=prov,
                    city="",
                    level=LEVEL_MAP.get(target_level, SchoolLevel.REGULAR),
                    category=SchoolCategory.GRAD_EXAM,
                    school_type=SchoolType.COMPREHENSIVE,
                    is_graduate_school=True,
                    description=f"kaoyan.cn id={school_id}",
                ))
                stats["inserted"] += 1
                print(f"  INSERT: {name} ({province_name})")
            else:
                # Report unmatched
                best = max(
                    ((n, SequenceMatcher(None, name, n).ratio()) for n in db_names),
                    key=lambda x: x[1],
                )
                unmatched.append((name, province_name, f"{best[0]} ({best[1]:.2f})"))
                stats["unmatched"] += 1

    db.commit()

    # --- Summary ---
    print(f"\n{'='*60}")
    print(f"Sync complete")
    for k, v in stats.items():
        print(f"  {k}: {v}")

    if unmatched:
        print(f"\n--- Unmatched kaoyan.cn schools ({len(unmatched)}) ---")
        for name, prov, best in unmatched:
            print(f"  {name} ({prov}) best={best}")

    # Distribution
    from sqlalchemy import func
    cats = (
        db.query(School.category, func.count())
        .group_by(School.category)
        .all()
    )
    print("\nBy category:")
    for cat, cnt in cats:
        print(f"  {cat.value if cat else 'NULL'}: {cnt}")

    levels = (
        db.query(School.level, func.count())
        .group_by(School.level)
        .all()
    )
    print("By level:")
    for lv, cnt in levels:
        print(f"  {lv.value if lv else 'NULL'}: {cnt}")

    grad_reg = (
        db.query(School)
        .filter(School.category == SchoolCategory.GRAD_EXAM)
        .count()
    )
    print(f"\n考研高校 total: {grad_reg}")

    # Write unmatched to file
    unmatched_path = KAOYAN_FILE.parent / "unmatched_schools.txt"
    with open(unmatched_path, "w", encoding="utf-8") as f:
        for name, prov, best in unmatched:
            f.write(f"{name}\t{prov}\t{best}\n")
    if unmatched:
        print(f"Unmatched list saved to {unmatched_path}")

    db.close()


if __name__ == "__main__":
    match_schools()
