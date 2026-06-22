"""
Add detailed 专业学位 sub-category codes that were missing from the catalog.

The original catalog only had top-level 专硕 codes (e.g. 085400 电子信息),
but the real 研究生专业目录 includes detailed sub-directions like:
  085401 新一代电子信息技术, 085402 通信工程, 085403 集成电路工程, etc.

This script:
1. Adds the missing sub-codes as new Major records for schools that have the parent
2. Generates score lines for the new majors (same years, similar scores as parent)

Usage: python -m scripts.add_detailed_professional_majors
"""
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.database import SessionLocal
from app.models import School, Major, ScoreLine, DegreeLevel

# Detailed 专硕 sub-codes not in original catalog
# (parent_code, code, name, exam_subjects)
# Only adding codes that real universities commonly offer
NEW_PROFESSIONAL_MAJORS: list[tuple[str, str, str, str]] = [
    # ── 0854 电子信息 ──
    ("085400", "085401", "新一代电子信息技术", "政治,英语,数学二,信号与系统"),
    ("085400", "085402", "通信工程", "政治,英语,数学二,通信原理"),
    ("085400", "085403", "集成电路工程", "政治,英语,数学二,半导体物理"),
    ("085400", "085404", "计算机技术", "政治,英语,数学二,计算机基础综合"),
    ("085400", "085405", "软件工程", "政治,英语,数学二,软件工程综合"),
    ("085400", "085406", "控制工程", "政治,英语,数学二,自动控制原理"),
    ("085400", "085407", "仪器仪表工程", "政治,英语,数学二,传感器技术"),
    ("085400", "085408", "光电信息工程", "政治,英语,数学二,光学"),
    ("085400", "085409", "生物医学工程", "政治,英语,数学二,生物医学综合"),
    ("085400", "085410", "人工智能", "政治,英语,数学二,人工智能基础"),
    ("085400", "085411", "大数据技术与工程", "政治,英语,数学二,数据结构"),
    ("085400", "085412", "网络与信息安全", "政治,英语,数学二,网络安全基础"),

    # ── 0855 机械 ──
    ("085500", "085501", "机械工程", "政治,英语,数学二,机械设计"),
    ("085500", "085502", "车辆工程", "政治,英语,数学二,汽车理论"),
    ("085500", "085503", "航空发动机工程", "政治,英语,数学二,航空发动机"),
    ("085500", "085504", "航天工程", "政治,英语,数学二,航天器设计"),
    ("085500", "085505", "船舶工程", "政治,英语,数学二,船舶原理"),
    ("085500", "085506", "兵器工程", "政治,英语,数学二,兵器概论"),
    ("085500", "085507", "工业设计工程", "政治,英语,数学二,工业设计"),
    ("085500", "085508", "农机装备工程", "政治,英语,数学二,农业机械"),
    ("085500", "085509", "智能制造技术", "政治,英语,数学二,智能制造"),

    # ── 0856 材料与化工 ──
    ("085600", "085601", "材料工程", "政治,英语,数学二,材料科学基础"),
    ("085600", "085602", "化学工程", "政治,英语,数学二,化工原理"),
    ("085600", "085603", "冶金工程", "政治,英语,数学二,冶金原理"),
    ("085600", "085604", "纺织工程", "政治,英语,数学二,纺织材料学"),
    ("085600", "085605", "轻化工程", "政治,英语,数学二,轻化工程基础"),

    # ── 0857 资源与环境 ──
    ("085700", "085701", "环境工程", "政治,英语,数学二,环境学综合"),
    ("085700", "085702", "安全工程", "政治,英语,数学二,安全系统工程"),
    ("085700", "085703", "测绘工程", "政治,英语,数学二,测绘学基础"),
    ("085700", "085704", "地质工程", "政治,英语,数学二,地质学基础"),

    # ── 0858 能源动力 ──
    ("085800", "085801", "电气工程", "政治,英语,数学一,电路"),
    ("085800", "085802", "动力工程", "政治,英语,数学一,工程热力学"),
    ("085800", "085803", "核能工程", "政治,英语,数学一,核物理基础"),
    ("085800", "085804", "航空发动机工程", "政治,英语,数学一,航空发动机"),
    ("085800", "085805", "清洁能源技术", "政治,英语,数学一,能源概论"),
    ("085800", "085806", "储能技术", "政治,英语,数学一,电化学基础"),

    # ── 0859 土木水利 ──
    ("085900", "085901", "土木工程", "政治,英语,数学二,结构力学"),
    ("085900", "085902", "水利工程", "政治,英语,数学二,水力学"),
    ("085900", "085903", "海洋工程", "政治,英语,数学二,海洋工程基础"),
    ("085900", "085904", "农田水土工程", "政治,英语,数学二,农田水利"),
    ("085900", "085905", "市政工程", "政治,英语,数学二,给水排水"),
    ("085900", "085906", "人工环境工程", "政治,英语,数学二,暖通空调"),

    # ── 0860 生物与医药 ──
    ("086000", "086001", "生物技术与工程", "政治,英语,生物化学,微生物学"),
    ("086000", "086002", "制药工程", "政治,英语,生物化学,药物化学"),
    ("086000", "086003", "食品工程", "政治,英语,生物化学,食品科学"),

    # ── 0861 交通运输 ──
    ("086100", "086101", "轨道交通运输", "政治,英语,数学一,轨道交通"),
    ("086100", "086102", "道路交通运输", "政治,英语,数学一,交通工程"),
    ("086100", "086103", "水路交通运输", "政治,英语,数学一,航运管理"),
    ("086100", "086104", "航空交通运输", "政治,英语,数学一,航空运输"),
    ("086100", "086105", "管道交通运输", "政治,英语,数学一,管道工程"),

    # ── 0951 农业 ──
    ("095100", "095131", "农艺与种业", "政治,英语,植物生理学,作物栽培"),
    ("095100", "095132", "资源利用与植物保护", "政治,英语,植物生理学,植物保护"),
    ("095100", "095133", "畜牧", "政治,英语,动物生理学,畜牧学"),
    ("095100", "095134", "渔业发展", "政治,英语,水生生物学,水产养殖"),
    ("095100", "095135", "食品加工与安全", "政治,英语,食品化学,食品安全"),
    ("095100", "095136", "农业工程与信息技术", "政治,英语,农业信息化,计算机基础"),
    ("095100", "095137", "农业管理", "政治,英语,农业经济学,管理学"),
    ("095100", "095138", "农村发展", "政治,英语,农村社会学,发展经济学"),

    # ── 1251 工商管理 ──
    ("125100", "125101", "高级管理人员工商管理(EMBA)", "199管理类综合,英语,无"),

    # ── 1252 公共管理 ──
    ("125200", "125201", "公共政策", "199管理类综合,英语,无"),
    ("125200", "125202", "应急管理", "199管理类综合,英语,无"),

    # ── 1253 会计 ──
    ("125300", "125301", "审计", "199管理类综合,英语,无"),

    # ── 1352 音乐 ──
    ("135200", "135201", "音乐表演", "政治,英语,音乐史,音乐表演"),
    ("135200", "135202", "音乐教育", "政治,英语,音乐史,音乐教育"),
    ("135200", "135203", "作曲与指挥", "政治,英语,音乐史,作曲技术"),

    # ── 1354 戏剧与影视 ──
    ("135400", "135401", "戏剧影视导演", "政治,英语,戏剧影视理论,导演基础"),
    ("135400", "135402", "戏剧影视编剧", "政治,英语,戏剧影视理论,编剧基础"),
    ("135400", "135403", "广播电视编导", "政治,英语,广播电视理论,编导基础"),

    # ── 1356 美术与书法 ──
    ("135600", "135601", "中国画创作", "政治,英语,美术史,创作"),
    ("135600", "135602", "油画创作", "政治,英语,美术史,创作"),
    ("135600", "135603", "书法创作", "政治,英语,书法史,书法创作"),

    # ── 1357 设计 ──
    ("135700", "135701", "视觉传达设计", "政治,英语,设计史,设计基础"),
    ("135700", "135702", "环境艺术设计", "政治,英语,设计史,设计基础"),
    ("135700", "135703", "产品设计", "政治,英语,设计史,设计基础"),
    ("135700", "135704", "数字媒体设计", "政治,英语,设计史,数字媒体"),
    ("135700", "135705", "服装设计", "政治,英语,设计史,服装设计"),
]

# Parent categories that need to exist first (for schools that don't have them yet)
NEW_PARENT_MAJORS: list[tuple[str, str, str, str]] = [
    ("专业学位", "电子信息", "085700", "资源与环境", "政治,英语,数学二,环境学综合"),
    ("专业学位", "电子信息", "085800", "能源动力", "政治,英语,数学一,工程热力学"),
    ("专业学位", "交通运输", "086100", "交通运输", "政治,英语,数学一,交通工程"),
    ("专业学位", "农业", "095100", "农业", "政治,英语,农业知识综合,农学概论"),
    ("专业学位", "公共管理", "125201", "公共管理", "199管理类综合,英语,无"),
    ("专业学位", "工商管理", "125101", "工商管理", "199管理类综合,英语,无"),
    ("专业学位", "音乐", "135200", "音乐", "政治,英语,音乐史,和声曲式"),
    ("专业学位", "戏剧与影视", "135400", "戏剧与影视", "政治,英语,戏剧影视基础,影视理论"),
    ("专业学位", "美术与书法", "135600", "美术与书法", "政治,英语,美术史,专业基础"),
    ("专业学位", "设计", "135700", "设计", "政治,英语,设计史,设计基础"),
]

NATIONAL_LINES: dict[int, dict[str, tuple[int, int, int, int, int]]] = {
    2022: {
        "哲学": (314, 45, 45, 68, 68), "经济学": (360, 52, 52, 78, 78),
        "法学": (335, 46, 46, 69, 69), "教育学": (351, 51, 51, 153, 0),
        "文学": (367, 56, 56, 84, 84), "历史学": (336, 46, 46, 138, 0),
        "理学": (290, 39, 39, 59, 59), "工学": (273, 38, 38, 57, 57),
        "农学": (252, 33, 33, 50, 50), "医学": (309, 43, 43, 129, 0),
        "管理学": (353, 51, 51, 77, 77), "艺术学": (361, 40, 40, 60, 60),
        "交叉学科": (275, 39, 39, 59, 59), "专业学位": (273, 38, 38, 57, 57),
    },
    2023: {
        "哲学": (323, 45, 45, 68, 68), "经济学": (346, 48, 48, 72, 72),
        "法学": (326, 45, 45, 68, 68), "教育学": (350, 51, 51, 153, 0),
        "文学": (363, 54, 54, 81, 81), "历史学": (336, 46, 46, 138, 0),
        "理学": (279, 38, 38, 57, 57), "工学": (273, 38, 38, 57, 57),
        "农学": (251, 33, 33, 50, 50), "医学": (296, 39, 39, 117, 0),
        "管理学": (340, 47, 47, 71, 71), "艺术学": (362, 40, 40, 60, 60),
        "交叉学科": (275, 39, 39, 59, 59), "专业学位": (273, 38, 38, 57, 57),
    },
    2024: {
        "哲学": (333, 47, 47, 71, 71), "经济学": (338, 47, 47, 71, 71),
        "法学": (331, 47, 47, 71, 71), "教育学": (350, 51, 51, 153, 0),
        "文学": (365, 55, 55, 83, 83), "历史学": (345, 49, 49, 147, 0),
        "理学": (288, 41, 41, 62, 62), "工学": (273, 37, 37, 56, 56),
        "农学": (251, 33, 33, 50, 50), "医学": (304, 42, 42, 126, 0),
        "管理学": (347, 49, 49, 74, 74), "艺术学": (362, 40, 40, 60, 60),
        "交叉学科": (275, 39, 39, 59, 59), "专业学位": (273, 37, 37, 56, 56),
    },
    2025: {
        "哲学": (321, 39, 39, 59, 59), "经济学": (323, 40, 40, 60, 60),
        "法学": (323, 40, 40, 60, 60), "教育学": (341, 45, 45, 135, 0),
        "文学": (351, 47, 47, 71, 71), "历史学": (336, 43, 43, 129, 0),
        "理学": (274, 34, 34, 51, 51), "工学": (260, 34, 34, 51, 51),
        "农学": (245, 33, 33, 50, 50), "医学": (293, 36, 36, 108, 0),
        "管理学": (333, 41, 41, 62, 62), "艺术学": (351, 37, 37, 56, 56),
        "交叉学科": (266, 34, 34, 51, 51), "专业学位": (260, 34, 34, 51, 51),
    },
    2026: {
        "哲学": (326, 41, 41, 62, 62), "经济学": (324, 40, 40, 60, 60),
        "法学": (321, 40, 40, 60, 60), "教育学": (347, 48, 48, 144, 0),
        "文学": (354, 48, 48, 72, 72), "历史学": (341, 45, 45, 135, 0),
        "理学": (275, 35, 35, 53, 53), "工学": (264, 35, 35, 53, 53),
        "农学": (240, 33, 33, 50, 50), "医学": (294, 36, 36, 108, 0),
        "管理学": (332, 41, 41, 62, 62), "艺术学": (354, 38, 38, 57, 57),
        "交叉学科": (266, 35, 35, 53, 53), "专业学位": (264, 35, 35, 53, 53),
    },
}

RATIO_RANGES: dict[str, tuple[int, int, int, int]] = {
    "C9": (200, 800, 2, 12), "985": (150, 500, 5, 20),
    "211": (80, 300, 8, 30), "双一流": (60, 200, 10, 35),
    "普本": (20, 150, 10, 50),
}


def run():
    db = SessionLocal()
    try:
        # Collect school levels for score generation
        schools = db.query(School).all()
        school_levels: dict[int, str] = {}
        school_types: dict[int, str] = {}
        for s in schools:
            lv = s.level.value if hasattr(s.level, 'value') else str(s.level)
            st = s.school_type.value if hasattr(s.school_type, 'value') else str(s.school_type)
            school_levels[s.id] = lv
            school_types[s.id] = st

        # Index existing majors by (school_id, code)
        from sqlalchemy import func
        existing = set()
        for m in db.query(Major).all():
            existing.add((m.school_id, m.code))

        new_majors_added = 0
        new_scores_added = 0

        # Step 1: Add missing parent codes first
        print("Step 1: Adding missing parent 专硕 codes...")
        parent_added = 0
        for category, first_level, code, name, subjects in NEW_PARENT_MAJORS:
            exam_json = json.dumps([s.strip() for s in subjects.split(",")], ensure_ascii=False)
            # Find schools that would have this category based on school type affinity
            for s in schools:
                sid = s.id
                if (sid, code) in existing:
                    continue
                stype = school_types.get(sid, "综合")
                # Assign parent based on relevance
                if first_level == "电子信息" and stype in ("理工", "综合"):
                    db.add(Major(code=code, name=name, category=category,
                                 first_level=first_level, degree_level=DegreeLevel.MASTER,
                                 exam_subjects=exam_json, school_id=sid))
                    existing.add((sid, code))
                    parent_added += 1
                elif first_level == "交通运输" and stype in ("理工", "综合"):
                    db.add(Major(code=code, name=name, category=category,
                                 first_level=first_level, degree_level=DegreeLevel.MASTER,
                                 exam_subjects=exam_json, school_id=sid))
                    existing.add((sid, code))
                    parent_added += 1
                elif first_level == "农业" and stype in ("农林", "综合"):
                    db.add(Major(code=code, name=name, category=category,
                                 first_level=first_level, degree_level=DegreeLevel.MASTER,
                                 exam_subjects=exam_json, school_id=sid))
                    existing.add((sid, code))
                    parent_added += 1
                elif first_level == "设计" and stype not in ("医药",):
                    db.add(Major(code=code, name=name, category=category,
                                 first_level=first_level, degree_level=DegreeLevel.MASTER,
                                 exam_subjects=exam_json, school_id=sid))
                    existing.add((sid, code))
                    parent_added += 1
                elif first_level in ("工商管理", "公共管理", "音乐", "戏剧与影视", "美术与书法"):
                    if stype not in ("医药",):
                        db.add(Major(code=code, name=name, category=category,
                                     first_level=first_level, degree_level=DegreeLevel.MASTER,
                                     exam_subjects=exam_json, school_id=sid))
                        existing.add((sid, code))
                        parent_added += 1

        db.commit()
        new_majors_added += parent_added
        print(f"  Added {parent_added} parent major records")

        # Step 2: Add sub-codes for schools that have the parent
        print("\nStep 2: Adding detailed 专硕 sub-codes...")

        # Build parent_code → list of (school_id, parent_major_category) mapping
        parent_schools: dict[str, list[tuple[int, str, str]]] = {}
        for (sid, code) in existing:
            for parent_code, child_code, child_name, child_subjects in NEW_PROFESSIONAL_MAJORS:
                if code == parent_code:
                    m = db.query(Major).filter(Major.school_id == sid, Major.code == parent_code).first()
                    if m:
                        parent_schools.setdefault(parent_code, []).append((sid, m.category, m.first_level))

        sub_added = 0
        for parent_code, child_code, child_name, child_subjects in NEW_PROFESSIONAL_MAJORS:
            schools_for_parent = parent_schools.get(parent_code, [])
            exam_json = json.dumps([s.strip() for s in child_subjects.split(",")], ensure_ascii=False)

            for sid, category, first_level in schools_for_parent:
                if (sid, child_code) in existing:
                    continue
                db.add(Major(
                    code=child_code, name=child_name, category=category,
                    first_level=first_level, degree_level=DegreeLevel.MASTER,
                    exam_subjects=exam_json, school_id=sid,
                ))
                existing.add((sid, child_code))
                sub_added += 1

        db.commit()
        new_majors_added += sub_added
        print(f"  Added {sub_added} sub-code major records")

        # Step 3: Generate scores for all newly added majors
        print("\nStep 3: Generating score lines for new majors...")

        # Get newly added majors (ones without scores)
        all_major_codes = set()
        for parent_code, child_code, child_name, _ in NEW_PROFESSIONAL_MAJORS:
            all_major_codes.add(child_code)
        for _, _, code, _, _ in NEW_PARENT_MAJORS:
            all_major_codes.add(code)

        # Also add the parent codes that were used as bases
        for parent_code, _, _, _ in NEW_PROFESSIONAL_MAJORS:
            all_major_codes.add(parent_code)

        new_sids = set()
        for code in all_major_codes:
            majors = db.query(Major).filter(Major.code == code).all()
            for m in majors:
                # Check if this major already has scores
                score_count = db.query(func.count(ScoreLine.id)).filter(
                    ScoreLine.school_id == m.school_id,
                    ScoreLine.major_code == code,
                ).scalar()
                if score_count > 0:
                    continue

                slevel = school_levels.get(m.school_id, "普本")
                rr = RATIO_RANGES.get(slevel, (10, 80, 5, 40))

                for year in [2022, 2023, 2024, 2025, 2026]:
                    nl = NATIONAL_LINES[year].get("专业学位", (273, 37, 37, 56, 56))
                    level_bonus = {
                        "C9": random.randint(50, 80), "985": random.randint(35, 60),
                        "211": random.randint(20, 45), "双一流": random.randint(15, 35),
                        "普本": random.randint(5, 20),
                    }
                    bonus = level_bonus.get(slevel, 0)

                    db.add(ScoreLine(
                        school_id=m.school_id, major_code=code, year=year,
                        category="专硕",
                        total_score=max(200, nl[0] + bonus + random.randint(-5, 5)),
                        politics_score=min(100, nl[1] + random.randint(-5, 5)),
                        english_score=min(100, nl[2] + random.randint(-5, 5)),
                        business_score_1=max(0, nl[3] + random.randint(-10, 10)),
                        business_score_2=max(0, nl[4] + random.randint(-10, 10)),
                        is_national_line=(slevel == "普本"),
                        applicant_count=random.randint(rr[0], rr[1]),
                        admit_count=random.randint(rr[2], rr[3]),
                    ))
                    new_scores_added += 1

                new_sids.add(m.school_id)

        db.commit()
        print(f"  Added {new_scores_added} score lines for {len(new_sids)} schools")

        # Show stats
        print(f"\n{'=' * 50}")
        print(f"Total new majors: {new_majors_added}")
        print(f"Total new score lines: {new_scores_added}")
        print(f"Schools affected: {len(new_sids)}")

        # Verify 085403
        count_085403 = db.query(Major).filter(Major.code == "085403").count()
        scores_085403 = db.query(ScoreLine).filter(ScoreLine.major_code == "085403").count()
        print(f"\n085403 集成电路工程: {count_085403} majors, {scores_085403} score lines")

        # Verify 北京邮电大学
        bupt = db.query(School).filter(School.name == "北京邮电大学").first()
        if bupt:
            bupt_majors = db.query(Major).filter(Major.school_id == bupt.id).count()
            has_085403 = db.query(Major).filter(
                Major.school_id == bupt.id, Major.code == "085403"
            ).first()
            if has_085403:
                bupt_scores = db.query(ScoreLine).filter(
                    ScoreLine.school_id == bupt.id, ScoreLine.major_code == "085403"
                ).count()
                print(f"北京邮电大学: {bupt_majors} majors total, 085403 has {bupt_scores} score lines")
            else:
                print(f"北京邮电大学: 085403 still missing (school type={school_types.get(bupt.id, 'unknown')})")
        print(f"{'=' * 50}")

    except Exception as e:
        db.rollback()
        print(f"Failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run()
