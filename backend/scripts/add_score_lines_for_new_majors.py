"""
Generate ScoreLine data for the newly-added engineering major codes.

Without ScoreLine data, these majors won't appear in the recommendation
pipeline (which is driven by trend data). Uses the same realistic score
generation logic as seed_majors_and_scores.py.

Usage: cd backend && PYTHONPATH=. python scripts/add_score_lines_for_new_majors.py
"""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from app.db.database import SessionLocal
from app.models import School, ScoreLine, SchoolCategory

NATIONAL_LINES: dict[int, dict[str, tuple[int, int, int, int, int]]] = {
    2022: {"工学": (273, 38, 38, 57, 57), "专业学位": (273, 38, 38, 57, 57)},
    2023: {"工学": (273, 38, 38, 57, 57), "专业学位": (273, 38, 38, 57, 57)},
    2024: {"工学": (273, 37, 37, 56, 56), "专业学位": (273, 37, 37, 56, 56)},
    2025: {"工学": (260, 35, 35, 53, 53), "专业学位": (260, 35, 35, 53, 53)},
    2026: {"工学": (265, 36, 36, 54, 54), "专业学位": (265, 36, 36, 54, 54)},
}

NEW_CODES = [
    "080600", "080601", "080602",
    "081500", "081501", "081502", "081503", "081504",
    "081600", "081601", "081602",
    "081800", "081801", "081802",
    "081900", "081901", "081902",
    "082000", "082001", "082002",
    "082100", "082101", "082102",
    "082200", "082201", "082202",
    "082400", "082401", "082402",
    "082500", "082501", "082502",
    "082600", "082601", "082602",
    "082700", "082701", "082702",
    "082800", "082801", "082802",
    "082900", "082901", "082902",
    "083200", "083201", "083202",
    "083300", "083400", "083600", "083700", "083800", "083900",
    "085100", "085700", "085800", "086100",
]

LEVEL_BONUS = {"C9": (50, 80), "985": (35, 60), "211": (20, 45), "双一流": (15, 35), "普本": (5, 20)}


def main():
    db = SessionLocal()
    try:
        schools = db.query(School).filter(
            School.category == SchoolCategory.GRAD_EXAM
        ).order_by(School.ranking_national.asc().nulls_last()).limit(50).all()

        if not schools:
            print("No GRAD_EXAM schools found.")
            return

        # Existing score_line (school_id, major_code, year) triples
        existing_triples = set()
        for code in NEW_CODES:
            rows = db.execute(
                text("SELECT DISTINCT school_id, year FROM score_lines WHERE major_code = :code"),
                {"code": code},
            ).fetchall()
            for (sid, yr) in rows:
                existing_triples.add((sid, code, yr))

        # Find schools that have these majors
        school_codes: dict[int, list[str]] = {}
        for school in schools:
            for code in NEW_CODES:
                row = db.execute(
                    text("SELECT 1 FROM majors WHERE school_id = :sid AND code = :code LIMIT 1"),
                    {"sid": school.id, "code": code},
                ).fetchone()
                if row:
                    school_codes.setdefault(school.id, []).append(code)

        if not school_codes:
            print("No schools have the new major codes. Run add_missing_engineering_majors.py first.")
            return

        print(f"{len(school_codes)} schools, {sum(len(v) for v in school_codes.values())} school×code pairs")

        inserted = 0
        for school in schools:
            codes = school_codes.get(school.id, [])
            if not codes:
                continue

            slevel = school.level.value if school.level else "普本"
            lo, hi = LEVEL_BONUS.get(slevel, (5, 15))

            for year in [2022, 2023, 2024, 2025, 2026]:
                for code in codes:
                    if (school.id, code, year) in existing_triples:
                        continue

                    is_prof = code[:2] == "08" and len(code) >= 3 and code[2] == "5"
                    cat = "专业学位" if is_prof else "工学"
                    base = NATIONAL_LINES[year][cat]
                    total, pol, eng, biz1, biz2 = base
                    bonus = random.randint(lo, hi)
                    year_adj = random.randint(-5, 5)

                    ts = max(200, total + bonus + year_adj)
                    ps = min(100, pol + random.randint(-5, 5))
                    es = min(100, eng + random.randint(-5, 5))
                    b1 = max(0, biz1 + random.randint(-10, 10))
                    b2 = max(0, biz2 + random.randint(-10, 10))

                    mult = random.uniform(1.05, 1.15)

                    db.add(ScoreLine(
                        school_id=school.id, major_code=code, year=year,
                        category="学硕" if not is_prof else "专硕",
                        total_score=ts, politics_score=ps, english_score=es,
                        business_score_1=b1, business_score_2=b2,
                        is_national_line=(slevel == "普本"),
                        re_exam_total_score=int(ts * mult),
                        re_exam_politics_score=min(100, int(ps * mult)),
                        re_exam_english_score=min(100, int(es * mult)),
                        re_exam_business_score_1=int(b1 * mult) if b1 > 0 else 0,
                        re_exam_business_score_2=int(b2 * mult) if b2 > 0 else 0,
                    ))
                    inserted += 1
                    existing_triples.add((school.id, code, year))

        db.commit()
        print(f"Inserted {inserted} score lines")
        print(f"Total score_lines: {db.query(ScoreLine).count()}")

    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
