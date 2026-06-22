"""Fix exam subjects: English (一/二) distinction + Math (一/二) for top-school 专硕.

Issues found:
  1. English: 576,115 majors use generic "英语" — not a single one has 英一/英二 distinction.
  2. Math: 4,170 085x/086x 专硕 at C9/985/211/双一流 all marked as 数学二,
     but top schools require 数学一 (e.g. 西电, 北邮, all 985).
  3. Combined: the recommendation pipeline sees "数一英一" user mismatching
     with "数学二+英语" school data, applying -23 penalty to all top schools.

Rules:
  English: 学硕 → 英一; 专硕(085x) → 英二; C9/985/211/双一流 专硕 override → 英一.
  Math:    085x/086x at C9/985/211/双一流 → 数学一; 普本 keep 数学二.
"""

import json
import sqlite3
import os
import sys

def fix_exam_subjects():
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_path = os.path.join(base, "gradschool.db")
    if not os.path.exists(db_path):
        # Try current directory
        db_path = "gradschool.db"

    db = sqlite3.connect(db_path)
    db.text_factory = str
    db.execute("PRAGMA journal_mode=WAL")

    # Category: which schools are elite (need 数一+英一 for 专硕)
    ELITE_LEVELS = {"C9", "NINE_EIGHT_FIVE", "TWO_ONE_ONE", "DOUBLE_FIRST_CLASS"}

    # Build school_id → level map
    school_levels = {}
    for sid, lvl in db.execute("SELECT id, level FROM schools WHERE level IS NOT NULL"):
        school_levels[sid] = lvl

    print(f"Loaded {len(school_levels)} school levels")

    # Count pre-fix state
    before_eng = db.execute(
        "SELECT COUNT(*) FROM majors WHERE exam_subjects IS NOT NULL AND exam_subjects != ''"
    ).fetchone()[0]
    before_eng1 = db.execute(
        "SELECT COUNT(*) FROM majors WHERE exam_subjects LIKE '%英语一%' OR exam_subjects LIKE '%英一%'"
    ).fetchone()[0]
    before_eng2 = db.execute(
        "SELECT COUNT(*) FROM majors WHERE exam_subjects LIKE '%英语二%' OR exam_subjects LIKE '%英二%'"
    ).fetchone()[0]
    before_math2_elite = db.execute("""
        SELECT COUNT(*) FROM majors m
        WHERE m.exam_subjects LIKE '%数学二%'
          AND (m.code LIKE '085%' OR m.code LIKE '086%')
          AND EXISTS (SELECT 1 FROM schools s WHERE s.id = m.school_id AND s.level IN ('C9','NINE_EIGHT_FIVE','TWO_ONE_ONE','DOUBLE_FIRST_CLASS'))
    """).fetchone()[0]

    print(f"\nBefore fix:")
    print(f"  Total with exam_subjects: {before_eng}")
    print(f"  英一/英语一: {before_eng1}")
    print(f"  英二/英语二: {before_eng2}")
    print(f"  085x/086x 数学二 at elite schools: {before_math2_elite}")

    # Fetch all majors that need checking (has exam_subjects)
    rows = db.execute("""
        SELECT m.id, m.code, m.school_id, m.exam_subjects
        FROM majors m
        WHERE m.exam_subjects IS NOT NULL AND m.exam_subjects != ''
    """).fetchall()

    print(f"\nProcessing {len(rows)} majors...")

    updates_eng = 0
    updates_math = 0
    batch = []
    BATCH_SIZE = 5000

    # 专硕 code patterns
    ZH_MASTER_PREFIXES = (
        "0854", "0855", "0856", "0857", "0858", "0859",
        "0860", "0861", "0862",  # 工程专硕
        "0951", "0952", "0953", "0954", "0955",  # 农业专硕
        "1051", "1052", "1053", "1054", "1055", "1056", "1057", "1058", "1059",  # 医学专硕
        "1251", "1252", "1253", "1254", "1255", "1256", "1257",  # 管理专硕
        "1351", "1352", "1353", "1354", "1355", "1356", "1357",  # 艺术专硕
        "1451", "1452", "1453",  # 交叉学科学位
    )

    def is_zhuan_master(code: str) -> bool:
        """Check if major code is a 专硕 (professional master's)."""
        if not code or len(code) < 4:
            return False
        return any(code.startswith(p) for p in ZH_MASTER_PREFIXES)

    def is_engineering_zhuan(code: str) -> bool:
        """Check if major code is an engineering 专硕 (085x or 086x)."""
        if not code or len(code) < 4:
            return False
        return code.startswith("085") or code.startswith("086")

    for mid, code, school_id, exam_json in rows:
        if not exam_json:
            continue

        try:
            subjects = json.loads(exam_json)
            if not isinstance(subjects, list) or len(subjects) == 0:
                continue
        except (json.JSONDecodeError, TypeError):
            continue

        modified = False
        lvl = school_levels.get(school_id, "")
        is_elite = lvl in ELITE_LEVELS
        is_zhuan = is_zhuan_master(code)
        is_eng_zhuan = is_engineering_zhuan(code)

        new_subjects = []
        for s in subjects:
            s_str = str(s).strip()

            # ── Fix English: 英语 → 英语一 or 英语二 ──
            if s_str == "英语":
                if is_zhuan:
                    if is_elite:
                        # Elite school 专硕 → 英语一
                        new_subjects.append("英语一")
                    else:
                        # Regular 专硕 → 英语二
                        new_subjects.append("英语二")
                else:
                    # 学硕 → 英语一
                    new_subjects.append("英语一")
                modified = True
                updates_eng += 1

            # ── Fix Math: 数学二 → 数学一 for engineering 专硕 at elite schools ──
            elif s_str == "数学二" and is_eng_zhuan and is_elite:
                new_subjects.append("数学一")
                modified = True
                updates_math += 1

            else:
                new_subjects.append(s_str)

        if modified:
            new_json = json.dumps(new_subjects, ensure_ascii=False)
            batch.append((new_json, mid))

            if len(batch) >= BATCH_SIZE:
                db.executemany(
                    "UPDATE majors SET exam_subjects = ? WHERE id = ?", batch
                )
                db.commit()
                print(f"  committed {len(batch)} updates...")
                batch.clear()

    # Final batch
    if batch:
        db.executemany(
            "UPDATE majors SET exam_subjects = ? WHERE id = ?", batch
        )
        db.commit()

    print(f"\n=== Fix Summary ===")
    print(f"  英语→英语一/二 updates: {updates_eng}")
    print(f"  数学二→数学一 (elite 085x/086x): {updates_math}")

    # Verify
    after_eng1 = db.execute(
        "SELECT COUNT(*) FROM majors WHERE exam_subjects LIKE '%英语一%' OR exam_subjects LIKE '%英一%'"
    ).fetchone()[0]
    after_eng2 = db.execute(
        "SELECT COUNT(*) FROM majors WHERE exam_subjects LIKE '%英语二%' OR exam_subjects LIKE '%英二%'"
    ).fetchone()[0]
    after_math2_elite = db.execute("""
        SELECT COUNT(*) FROM majors m
        WHERE m.exam_subjects LIKE '%数学二%'
          AND (m.code LIKE '085%' OR m.code LIKE '086%')
          AND EXISTS (SELECT 1 FROM schools s WHERE s.id = m.school_id AND s.level IN ('C9','NINE_EIGHT_FIVE','TWO_ONE_ONE','DOUBLE_FIRST_CLASS'))
    """).fetchone()[0]
    after_gen_eng = db.execute(
        "SELECT COUNT(*) FROM majors WHERE exam_subjects LIKE '%\"英语\"%'"
    ).fetchone()[0]

    print(f"\nAfter fix:")
    print(f"  英语一: {after_eng1}")
    print(f"  英语二: {after_eng2}")
    print(f"  通用英语 remaining: {after_gen_eng} (should be 0)")
    print(f"  085x/086x 数学二 at elite: {after_math2_elite} (should be 0)")

    # Sample verification
    print("\n=== Spot checks ===")
    checks = [
        ("西安电子科技大学", "085401", "数一+英一"),
        ("西安电子科技大学", "085402", "数一+英一"),
        ("清华大学", "085400", "数一+英一"),
        ("北京大学", "010100", "英一(学硕)"),
        ("西安理工大学", "085400", "数二+英二"),  # 普本, should stay 数二+英二
    ]
    for sname, mcode, expected in checks:
        row = db.execute("""
            SELECT m.exam_subjects FROM majors m
            JOIN schools s ON m.school_id = s.id
            WHERE s.name = ? AND m.code = ?
        """, [sname, mcode]).fetchone()
        if row:
            print(f"  {sname} {mcode}: {row[0][:80] if row[0] else 'NULL'}  (expected: {expected})")
        else:
            print(f"  {sname} {mcode}: NOT FOUND")

    db.close()
    print("\nDone.")

if __name__ == "__main__":
    fix_exam_subjects()
