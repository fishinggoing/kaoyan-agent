"""
Add missing engineering (08xx) graduate majors to the database.

The seed_majors_and_scores.py MAJOR_CATALOG was missing 22 sub-disciplines
between 083501 and the 专硕 section. This script inserts only the missing
codes — existing majors are left untouched.

Usage: python -m scripts.add_missing_engineering_majors
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.database import SessionLocal
from sqlalchemy import text

from app.models import School, Major, DegreeLevel, SchoolCategory

# Mirror the definitions in seed_majors_and_scores.py MAJOR_CATALOG.
NEW_MAJORS: list[tuple[str, str, str, str, str]] = [
    # ── 08 工学 学硕 (补全) ──
    ("工学", "冶金工程", "080600", "冶金物理化学", "政治,英语,数学一,冶金原理"),
    ("工学", "冶金工程", "080601", "钢铁冶金", "政治,英语,数学一,钢铁冶金"),
    ("工学", "冶金工程", "080602", "有色金属冶金", "政治,英语,数学一,有色冶金"),
    ("工学", "水利工程", "081500", "水文学及水资源", "政治,英语,数学一,水文学"),
    ("工学", "水利工程", "081501", "水力学及河流动力学", "政治,英语,数学一,流体力学"),
    ("工学", "水利工程", "081502", "水工结构工程", "政治,英语,数学一,结构力学"),
    ("工学", "水利工程", "081503", "水利水电工程", "政治,英语,数学一,水力学"),
    ("工学", "水利工程", "081504", "港口海岸及近海工程", "政治,英语,数学一,海岸工程"),
    ("工学", "测绘科学与技术", "081600", "大地测量学与测量工程", "政治,英语,数学一,测绘科学"),
    ("工学", "测绘科学与技术", "081601", "摄影测量与遥感", "政治,英语,数学一,遥感原理"),
    ("工学", "测绘科学与技术", "081602", "地图制图学与地理信息工程", "政治,英语,数学一,GIS原理"),
    ("工学", "地质资源与地质工程", "081800", "矿产普查与勘探", "政治,英语,数学二,地质学"),
    ("工学", "地质资源与地质工程", "081801", "地球探测与信息技术", "政治,英语,数学二,地球物理"),
    ("工学", "地质资源与地质工程", "081802", "地质工程", "政治,英语,数学二,工程地质"),
    ("工学", "矿业工程", "081900", "采矿工程", "政治,英语,数学二,采矿学"),
    ("工学", "矿业工程", "081901", "矿物加工工程", "政治,英语,数学二,矿物加工"),
    ("工学", "矿业工程", "081902", "安全技术及工程", "政治,英语,数学二,安全工程"),
    ("工学", "石油与天然气工程", "082000", "油气井工程", "政治,英语,数学二,钻井工程"),
    ("工学", "石油与天然气工程", "082001", "油气田开发工程", "政治,英语,数学二,油藏工程"),
    ("工学", "石油与天然气工程", "082002", "油气储运工程", "政治,英语,数学二,油气储运"),
    ("工学", "纺织科学与工程", "082100", "纺织工程", "政治,英语,数学二,纺织材料"),
    ("工学", "纺织科学与工程", "082101", "纺织材料与纺织品设计", "政治,英语,数学二,纺织材料"),
    ("工学", "纺织科学与工程", "082102", "服装设计与工程", "政治,英语,数学二,服装材料"),
    ("工学", "轻工技术与工程", "082200", "制浆造纸工程", "政治,英语,数学二,化工原理"),
    ("工学", "轻工技术与工程", "082201", "制糖工程", "政治,英语,数学二,化工原理"),
    ("工学", "轻工技术与工程", "082202", "发酵工程", "政治,英语,数学二,生物化学"),
    ("工学", "船舶与海洋工程", "082400", "船舶与海洋结构物设计制造", "政治,英语,数学一,船舶原理"),
    ("工学", "船舶与海洋工程", "082401", "轮机工程", "政治,英语,数学一,轮机工程"),
    ("工学", "船舶与海洋工程", "082402", "水声工程", "政治,英语,数学一,声学基础"),
    ("工学", "航空宇航科学与技术", "082500", "飞行器设计", "政治,英语,数学一,飞行器设计"),
    ("工学", "航空宇航科学与技术", "082501", "航空宇航推进理论与工程", "政治,英语,数学一,航空发动机"),
    ("工学", "航空宇航科学与技术", "082502", "航空宇航制造工程", "政治,英语,数学一,制造工程"),
    ("工学", "兵器科学与技术", "082600", "武器系统与运用工程", "政治,英语,数学一,武器系统"),
    ("工学", "兵器科学与技术", "082601", "兵器发射理论与技术", "政治,英语,数学一,弹道学"),
    ("工学", "兵器科学与技术", "082602", "军事化学与烟火技术", "政治,英语,数学一,火炸药"),
    ("工学", "核科学与技术", "082700", "核能科学与工程", "政治,英语,数学一,核物理"),
    ("工学", "核科学与技术", "082701", "核燃料循环与材料", "政治,英语,数学一,核材料"),
    ("工学", "核科学与技术", "082702", "辐射防护与环境保护", "政治,英语,数学一,辐射防护"),
    ("工学", "农业工程", "082800", "农业机械化工程", "政治,英语,数学二,农业机械"),
    ("工学", "农业工程", "082801", "农业水土工程", "政治,英语,数学二,土壤水文学"),
    ("工学", "农业工程", "082802", "农业电气化与自动化", "政治,英语,数学二,电工电子"),
    ("工学", "林业工程", "082900", "森林工程", "政治,英语,数学二,森林工程"),
    ("工学", "林业工程", "082901", "木材科学与技术", "政治,英语,数学二,木材科学"),
    ("工学", "林业工程", "082902", "林产化学加工工程", "政治,英语,数学二,林产化工"),
    ("工学", "食品科学与工程", "083200", "食品科学", "政治,英语,数学二,食品化学"),
    ("工学", "食品科学与工程", "083201", "农产品加工及贮藏工程", "政治,英语,数学二,食品工程"),
    ("工学", "食品科学与工程", "083202", "水产品加工及贮藏工程", "政治,英语,数学二,食品工程"),
    ("工学", "城乡规划学", "083300", "城乡规划学", "政治,英语,规划原理,规划设计"),
    ("工学", "风景园林学", "083400", "风景园林学", "政治,英语,园林设计,植物学"),
    ("工学", "生物工程", "083600", "生物工程", "政治,英语,数学二,生物化学"),
    ("工学", "安全科学与工程", "083700", "安全科学与工程", "政治,英语,数学二,安全工程"),
    ("工学", "公安技术", "083800", "公安技术", "政治,英语,数学二,公安技术"),
    ("工学", "网络空间安全", "083900", "网络空间安全", "政治,英语,数学一,网络安全"),

    # ── 08 工学 专硕 (补全) ──
    ("专业学位", "建筑学", "085100", "建筑学", "政治,英语,建筑学基础,建筑设计"),
    ("专业学位", "资源与环境", "085700", "资源与环境", "政治,英语,数学二,环境学综合"),
    ("专业学位", "能源动力", "085800", "能源动力", "政治,英语,数学二,工程热力学"),
    ("专业学位", "交通运输", "086100", "交通运输", "政治,英语,数学二,交通工程"),
]


def main():
    db = SessionLocal()
    try:
        # Get existing codes to skip
        existing = {r[0] for r in db.execute(
            text("SELECT code FROM majors")
        ).fetchall()}

        # Get 考研高校 for assignment
        grad_schools = db.query(School).filter(
            School.category == SchoolCategory.GRAD_EXAM
        ).order_by(School.ranking_national.asc().nulls_last()).limit(50).all()

        if not grad_schools:
            print("No GRAD_EXAM schools found. Run school reclassification first.")
            return

        inserted = 0
        skipped = 0
        for category, first_level, code, name, exam_subjects in NEW_MAJORS:
            if code in existing:
                skipped += 1
                continue

            # Assign this major to top-N matching-type schools
            # Each school type may favor different majors
            major = Major(
                category=category,
                first_level=first_level,
                code=code,
                name=name,
                degree_level=DegreeLevel.MASTER,
                exam_subjects=exam_subjects,
                school_id=grad_schools[0].id,  # Assign to first school initially
            )
            db.add(major)
            inserted += 1

            # Also assign to a few more schools for breadth
            for s in grad_schools[1:12]:
                db.add(Major(
                    category=category,
                    first_level=first_level,
                    code=code,
                    name=name,
                    degree_level=DegreeLevel.MASTER,
                    exam_subjects=exam_subjects,
                    school_id=s.id,
                ))

        db.commit()
        print(f"Inserted {inserted} new major codes × 12 schools = {inserted * 12} rows")
        print(f"Skipped {skipped} already-existing codes")

    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
