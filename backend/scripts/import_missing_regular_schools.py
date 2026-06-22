"""
Import all missing 考研高校 from crawled data.
- Military schools → MILITARY level
- Sino-foreign (HK/Macau/foreign JV) → SINO_FOREIGN level
- Other regular universities → REGULAR level
Only records school name + level + province — no major/exam data.
"""

import json
import os
import sys
import io

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from app.db.database import SessionLocal
from app.models import School, SchoolLevel, SchoolCategory

# ── Load crawled data ──
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CRAWLED_PATH = os.path.join(PROJECT_ROOT, "crawler_data", "kaoyan_cn", "schools_raw.json")
with open(CRAWLED_PATH, "r", encoding="utf-8") as f:
    raw = json.load(f)
crawled = raw["schools"]

# ── Exclusion keywords for non-GRAD_EXAM ──
ADULT_KW = [
    "继续教育", "成人教育", "网络教育", "开放大学", "广播电视大学",
    "职工大学", "业余", "函授", "夜大学", "进修学院", "培训", "专修",
]
VOCATIONAL_KW = [
    "职业技术学院", "高等专科学校", "职业学院", "技师学院", "技工学校",
]

# ── Military keywords ──
MILITARY_KW = [
    "解放军", "陆军", "海军", "空军", "火箭军", "武警", "国防",
    "军事", "战略支援", "信息支援", "网络空间", "联合勤务",
    "军事航天", "部队工程",
]

# ── Sino-foreign keywords ──
SINO_FOREIGN_KW = [
    "香港", "澳门", "诺丁汉", "杜克", "肯恩", "利物浦",
    "以色列", "莫斯科", "佐治亚", "北师香港浸会",
]

# ── Name corrections for matching ──
NAME_CORRECTIONS = {
    "中国人民解放军国防科技大学": "国防科技大学",
    "中国人民解放军空军军医大学": "空军军医大学",
    "中国人民解放军海军军医大学": "海军军医大学",
}


def is_grad_exam(name: str) -> bool:
    for kw in ADULT_KW + VOCATIONAL_KW:
        if kw in name:
            return False
    return True


def classify_level(school: dict) -> SchoolLevel:
    name = school["school_name"]
    if school["is_985"] == 1:
        return SchoolLevel.NINE_EIGHT_FIVE
    if school["is_211"] == 1:
        return SchoolLevel.TWO_ONE_ONE
    if school["syl"] == 1:
        return SchoolLevel.DOUBLE_FIRST_CLASS
    for kw in MILITARY_KW:
        if kw in name:
            return SchoolLevel.MILITARY
    for kw in SINO_FOREIGN_KW:
        if kw in name:
            return SchoolLevel.SINO_FOREIGN
    return SchoolLevel.REGULAR


def main():
    db = SessionLocal()

    # Get existing school names
    existing = {s.name for s in db.query(School).all()}

    grad_schools = [s for s in crawled if is_grad_exam(s["school_name"])]

    # Build lookup by name
    name_map = {s["school_name"]: s for s in grad_schools}

    to_add = []
    stats = {
        SchoolLevel.MILITARY: [],
        SchoolLevel.SINO_FOREIGN: [],
        SchoolLevel.REGULAR: [],
    }

    for s in grad_schools:
        name = s["school_name"]
        corrected = NAME_CORRECTIONS.get(name, name)
        if corrected in existing:
            continue
        level = classify_level(s)
        stats[level].append(name)
        to_add.append(School(
            name=name,
            province=s.get("province_name"),
            level=level,
            category=SchoolCategory.GRAD_EXAM,
        ))

    # Print categorization
    for level, names in stats.items():
        print(f"\n{'='*60}")
        print(f"  {level.value} ({len(names)} 所)")
        print(f"{'='*60}")
        for n in sorted(names):
            print(f"  {n}")

    print(f"\n{'='*60}")
    print(f"  共计新增: {len(to_add)} 所")
    print(f"  军事院校: {len(stats[SchoolLevel.MILITARY])}")
    print(f"  中外合作: {len(stats[SchoolLevel.SINO_FOREIGN])}")
    print(f"  普本:     {len(stats[SchoolLevel.REGULAR])}")

    if not to_add:
        print("\n没有需要新增的学校。")
        db.close()
        return

    print(f"\n开始写入数据库...")
    db.add_all(to_add)
    db.commit()

    # Verify
    total = db.query(School).filter(School.category == SchoolCategory.GRAD_EXAM).count()
    print(f"\n数据库 GRAD_EXAM 学校总数: {total}")

    db.close()
    print("完成。")


if __name__ == "__main__":
    main()
