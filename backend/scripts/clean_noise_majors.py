"""Clean noise majors using SQLAlchemy (avoid raw sqlite3 issues)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.db.database import SessionLocal

SCHOOL_TYPE_EXCLUDE = {
    "FINANCE_ECONOMICS": ["08"],
    "LANGUAGE_LAW": ["08"],
    "ART_SPORTS": ["08"],
    "MEDICAL": ["07", "08"],
}
NAME_NOISE_KW = ["财经", "政法", "外国语", "语言", "美术", "音乐", "体育", "艺术", "戏剧", "电影", "舞蹈", "戏曲"]

def clean():
    db = SessionLocal()

    # Get all GRAD_EXAM schools
    rows = db.execute(
        text("SELECT id, name, school_type FROM schools WHERE category = 'GRAD_EXAM'")
    ).fetchall()
    schools = {r[0]: (r[1], r[2] or "") for r in rows}
    print(f"Loaded {len(schools)} schools")

    # Identify noise
    pairs = []
    for sid, (name, stype) in schools.items():
        prefixes = set()
        if stype in SCHOOL_TYPE_EXCLUDE:
            prefixes.update(SCHOOL_TYPE_EXCLUDE[stype])
        if any(kw in name for kw in NAME_NOISE_KW):
            prefixes.add("08")

        for pfx in prefixes:
            codes = db.execute(
                text(f"SELECT code FROM majors WHERE school_id = :sid AND code LIKE :pfx"),
                {"sid": sid, "pfx": f"{pfx}%"},
            ).fetchall()
            for (code,) in codes:
                pairs.append((sid, code))

    print(f"Noise pairs: {len(pairs)}")

    # Count before
    before_m = db.execute(text("SELECT COUNT(*) FROM majors")).scalar()
    before_sl = db.execute(text("SELECT COUNT(*) FROM score_lines")).scalar()
    print(f"Before: majors={before_m}, score_lines={before_sl}")

    # Delete
    for i, (sid, code) in enumerate(pairs):
        db.execute(
            text("DELETE FROM score_lines WHERE school_id = :sid AND major_code = :code"),
            {"sid": sid, "code": code},
        )
        db.execute(
            text("DELETE FROM majors WHERE school_id = :sid AND code = :code"),
            {"sid": sid, "code": code},
        )
        if (i + 1) % 5000 == 0:
            db.commit()
            print(f"  {i + 1}/{len(pairs)}...")

    db.commit()

    after_m = db.execute(text("SELECT COUNT(*) FROM majors")).scalar()
    after_sl = db.execute(text("SELECT COUNT(*) FROM score_lines")).scalar()
    print(f"Majors:    {before_m:>8,d} -> {after_m:>8,d} (-{before_m - after_m:,d})")
    print(f"ScoreLines:{before_sl:>8,d} -> {after_sl:>8,d} (-{before_sl - after_sl:,d})")

    # Spot checks
    checks = [
        ("上海财经大学", "085400", False),
        ("西安电子科技大学", "085401", True),
        ("北京邮电大学", "085402", True),
        ("华东师范大学", "085400", True),
        ("中国政法大学", "085400", False),
        ("中央美术学院", "085400", False),
        ("上海财经大学", "020200", True),
    ]
    print("\nSpot checks:")
    for sname, code, expect in checks:
        row = db.execute(
            text("SELECT COUNT(*) FROM majors WHERE school_id = (SELECT id FROM schools WHERE name = :n) AND code = :c"),
            {"n": sname, "c": code},
        ).fetchone()
        exists = row[0] > 0
        ok = "OK" if exists == expect else "FAIL"
        print(f"  [{ok}] {sname:20s} {code}: exists={exists} expected={expect}")

    db.close()
    print("Done.")

if __name__ == "__main__":
    clean()
