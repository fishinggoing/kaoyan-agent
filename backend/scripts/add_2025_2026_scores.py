"""
Add 2025 and 2026 score line data based on actual national lines.

For each existing (school_id, major_code) that has 2024 scores,
generates 2025 and 2026 scores adjusted by real national line changes.

Usage: python -m scripts.add_2025_2026_scores
"""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.database import SessionLocal
from app.models import School, Major, ScoreLine, SchoolLevel

# National lines: (total, politics, english, biz1, biz2)
NATIONAL_LINES: dict[int, dict[str, tuple[int, int, int, int, int]]] = {
    2024: {
        "哲学": (333, 47, 47, 71, 71),
        "经济学": (338, 47, 47, 71, 71),
        "法学": (331, 47, 47, 71, 71),
        "教育学": (350, 51, 51, 153, 0),
        "文学": (365, 55, 55, 83, 83),
        "历史学": (345, 49, 49, 147, 0),
        "理学": (288, 41, 41, 62, 62),
        "工学": (273, 37, 37, 56, 56),
        "农学": (251, 33, 33, 50, 50),
        "医学": (304, 42, 42, 126, 0),
        "管理学": (347, 49, 49, 74, 74),
        "艺术学": (362, 40, 40, 60, 60),
        "交叉学科": (275, 39, 39, 59, 59),
        "专业学位": (273, 37, 37, 56, 56),
    },
    2025: {
        "哲学": (321, 39, 39, 59, 59),
        "经济学": (323, 40, 40, 60, 60),
        "法学": (323, 40, 40, 60, 60),
        "教育学": (341, 45, 45, 135, 0),
        "文学": (351, 47, 47, 71, 71),
        "历史学": (336, 43, 43, 129, 0),
        "理学": (274, 34, 34, 51, 51),
        "工学": (260, 34, 34, 51, 51),
        "农学": (245, 33, 33, 50, 50),
        "医学": (293, 36, 36, 108, 0),
        "管理学": (333, 41, 41, 62, 62),
        "艺术学": (351, 37, 37, 56, 56),
        "交叉学科": (266, 34, 34, 51, 51),
        "专业学位": (260, 34, 34, 51, 51),
    },
    2026: {
        "哲学": (326, 41, 41, 62, 62),
        "经济学": (324, 40, 40, 60, 60),
        "法学": (321, 40, 40, 60, 60),
        "教育学": (347, 48, 48, 144, 0),
        "文学": (354, 48, 48, 72, 72),
        "历史学": (341, 45, 45, 135, 0),
        "理学": (275, 35, 35, 53, 53),
        "工学": (264, 35, 35, 53, 53),
        "农学": (240, 33, 33, 50, 50),
        "医学": (294, 36, 36, 108, 0),
        "管理学": (332, 41, 41, 62, 62),
        "艺术学": (354, 38, 38, 57, 57),
        "交叉学科": (266, 35, 35, 53, 53),
        "专业学位": (264, 35, 35, 53, 53),
    },
}


def migrate():
    db = SessionLocal()
    try:
        existing_2025 = db.query(ScoreLine).filter(ScoreLine.year == 2025).count()
        existing_2026 = db.query(ScoreLine).filter(ScoreLine.year == 2026).count()

        if existing_2025 > 0 and existing_2026 > 0:
            print(f"Already have {existing_2025} (2025) + {existing_2026} (2026) score lines. Skipping.")
            db.close()
            return

        # Build category lookup from Major table
        major_categories: dict[str, str] = {}
        for m in db.query(Major).all():
            cat = m.category if m.category else "专业学位"
            major_categories[m.code] = cat

        # Get all 2024 scores and group by (school_id, major_code)
        scores_2024 = db.query(ScoreLine).filter(ScoreLine.year == 2024).all()
        print(f"Found {len(scores_2024)} records for 2024")

        # Build school-level map
        school_levels: dict[int, str] = {}
        for s in db.query(School).all():
            lv = s.level.value if hasattr(s.level, 'value') else str(s.level)
            school_levels[s.id] = lv

        # Level bonus ranges (same as original seed)
        level_bonus_range: dict[str, tuple[int, int]] = {
            "C9": (50, 80),
            "985": (35, 60),
            "211": (20, 45),
            "双一流": (15, 35),
            "省属重点": (5, 20),
            "普通": (-5, 10),
        }

        added_2025 = 0
        added_2026 = 0

        for s24 in scores_2024:
            cat = major_categories.get(s24.major_code, "专业学位")
            slevel = school_levels.get(s24.school_id, "普通")

            nl_2024 = NATIONAL_LINES[2024].get(cat, (273, 37, 37, 56, 56))
            nl_2025 = NATIONAL_LINES[2025].get(cat, (260, 34, 34, 51, 51))
            nl_2026 = NATIONAL_LINES[2026].get(cat, (264, 35, 35, 53, 53))

            bonus_lo, bonus_hi = level_bonus_range.get(slevel, (-5, 10))

            for target_year, nl_target in [(2025, nl_2025), (2026, nl_2026)]:
                # Compute how much the national line shifted
                shift_total = nl_target[0] - nl_2024[0]

                # Adjust school score relative to national line shift
                new_total = max(200, s24.total_score + shift_total + random.randint(-3, 3))

                # Per-subject shifts
                new_pol = min(100, max(0, (s24.politics_score or 0) + (nl_target[1] - nl_2024[1]) + random.randint(-2, 2)))
                new_eng = min(100, max(0, (s24.english_score or 0) + (nl_target[2] - nl_2024[2]) + random.randint(-2, 2)))
                new_biz1 = max(0, (s24.business_score_1 or 0) + (nl_target[3] - nl_2024[3]) + random.randint(-3, 3))
                new_biz2 = max(0, (s24.business_score_2 or 0) + (nl_target[4] - nl_2024[4]) + random.randint(-3, 3))

                db.add(ScoreLine(
                    school_id=s24.school_id,
                    major_code=s24.major_code,
                    year=target_year,
                    category=s24.category,
                    total_score=new_total,
                    politics_score=new_pol,
                    english_score=new_eng,
                    business_score_1=new_biz1,
                    business_score_2=new_biz2,
                    is_national_line=s24.is_national_line,
                ))

                if target_year == 2025:
                    added_2025 += 1
                else:
                    added_2026 += 1

            if (added_2025 + added_2026) % 5000 == 0:
                db.commit()
                print(f"  {added_2025 + added_2026} records inserted...")

        db.commit()
        print(f"\nDone: added {added_2025} (2025) + {added_2026} (2026) score lines")
        total = db.query(ScoreLine).count()
        years = db.query(ScoreLine.year).distinct().all()
        print(f"Total score lines: {total}, years: {[y[0] for y in years]}")

    except Exception as e:
        db.rollback()
        print(f"Migration failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    migrate()
