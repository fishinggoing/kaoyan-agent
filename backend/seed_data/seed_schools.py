"""
种子数据脚本 — 导入初始院校和分数线数据。

数据来源: 公开的全国研究生招生院校列表 + 历年国家线数据。
运行: python -m seed_data.seed_schools (from backend/)
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import SessionLocal, engine, Base
from app.models import School, Major, ScoreLine, SchoolLevel, SchoolType, DegreeLevel

# 初始院校数据（公开信息）
INITIAL_SCHOOLS = [
    # C9
    {"name": "清华大学", "province": "北京", "city": "北京", "level": SchoolLevel.C9, "school_type": SchoolType.COMPREHENSIVE, "is_graduate_school": True, "ranking_national": 1, "website": "https://www.tsinghua.edu.cn", "graduate_school_url": "https://yz.tsinghua.edu.cn", "description": "中国顶尖综合性研究型大学，工科实力全国第一。"},
    {"name": "北京大学", "province": "北京", "city": "北京", "level": SchoolLevel.C9, "school_type": SchoolType.COMPREHENSIVE, "is_graduate_school": True, "ranking_national": 2, "website": "https://www.pku.edu.cn", "graduate_school_url": "https://admission.pku.edu.cn", "description": "中国最著名的高等学府之一，文理医工全面发展。"},
    {"name": "浙江大学", "province": "浙江", "city": "杭州", "level": SchoolLevel.C9, "school_type": SchoolType.COMPREHENSIVE, "is_graduate_school": True, "ranking_national": 3, "website": "https://www.zju.edu.cn", "graduate_school_url": "https://grs.zju.edu.cn", "description": "综合性研究型大学，工科和农学实力突出。"},
    {"name": "上海交通大学", "province": "上海", "city": "上海", "level": SchoolLevel.C9, "school_type": SchoolType.COMPREHENSIVE, "is_graduate_school": True, "ranking_national": 4, "website": "https://www.sjtu.edu.cn", "graduate_school_url": "https://www.gs.sjtu.edu.cn", "description": "以工科、医科见长的综合性大学，国际化程度高。"},
    {"name": "复旦大学", "province": "上海", "city": "上海", "level": SchoolLevel.C9, "school_type": SchoolType.COMPREHENSIVE, "is_graduate_school": True, "ranking_national": 5, "website": "https://www.fudan.edu.cn", "graduate_school_url": "https://gs.fudan.edu.cn", "description": "文理医经管全面发展的综合性研究型大学。"},
    {"name": "南京大学", "province": "江苏", "city": "南京", "level": SchoolLevel.C9, "school_type": SchoolType.COMPREHENSIVE, "is_graduate_school": True, "ranking_national": 6, "website": "https://www.nju.edu.cn", "graduate_school_url": "https://grawww.nju.edu.cn", "description": "历史悠久的研究型大学，文理科基础扎实。"},
    {"name": "中国科学技术大学", "province": "安徽", "city": "合肥", "level": SchoolLevel.C9, "school_type": SchoolType.SCIENCE_ENGINEERING, "is_graduate_school": True, "ranking_national": 7, "website": "https://www.ustc.edu.cn", "graduate_school_url": "https://gradschool.ustc.edu.cn", "description": "中国科学院直属，以前沿科学和高新技术为主。"},
    {"name": "哈尔滨工业大学", "province": "黑龙江", "city": "哈尔滨", "level": SchoolLevel.C9, "school_type": SchoolType.SCIENCE_ENGINEERING, "is_graduate_school": True, "ranking_national": 8, "website": "https://www.hit.edu.cn", "graduate_school_url": "https://yzb.hit.edu.cn", "description": "航天和工科闻名，国防七子之一。"},
    {"name": "西安交通大学", "province": "陕西", "city": "西安", "level": SchoolLevel.C9, "school_type": SchoolType.COMPREHENSIVE, "is_graduate_school": True, "ranking_national": 9, "website": "https://www.xjtu.edu.cn", "graduate_school_url": "https://yz.xjtu.edu.cn", "description": "西部地区最好的大学，工科和管理学科实力强。"},

    # 985
    {"name": "武汉大学", "province": "湖北", "city": "武汉", "level": SchoolLevel.NINE_EIGHT_FIVE, "school_type": SchoolType.COMPREHENSIVE, "is_graduate_school": True, "ranking_national": 10, "website": "https://www.whu.edu.cn", "graduate_school_url": "https://gs.whu.edu.cn", "description": "综合性大学，法学、测绘、遥感等领域全国领先。"},
    {"name": "华中科技大学", "province": "湖北", "city": "武汉", "level": SchoolLevel.NINE_EIGHT_FIVE, "school_type": SchoolType.SCIENCE_ENGINEERING, "is_graduate_school": True, "ranking_national": 11, "website": "https://www.hust.edu.cn", "graduate_school_url": "https://gs.hust.edu.cn", "description": "以工科和医科见长，光电子和机械领域突出。"},
    {"name": "中山大学", "province": "广东", "city": "广州", "level": SchoolLevel.NINE_EIGHT_FIVE, "school_type": SchoolType.COMPREHENSIVE, "is_graduate_school": True, "ranking_national": 12, "website": "https://www.sysu.edu.cn", "graduate_school_url": "https://graduate.sysu.edu.cn", "description": "华南地区最好的综合性大学，医学实力强。"},
    {"name": "四川大学", "province": "四川", "city": "成都", "level": SchoolLevel.NINE_EIGHT_FIVE, "school_type": SchoolType.COMPREHENSIVE, "is_graduate_school": True, "ranking_national": 13, "website": "https://www.scu.edu.cn", "graduate_school_url": "https://yz.scu.edu.cn", "description": "西部地区规模最大的综合性大学，华西医学中心闻名全国。"},
    {"name": "北京航空航天大学", "province": "北京", "city": "北京", "level": SchoolLevel.NINE_EIGHT_FIVE, "school_type": SchoolType.SCIENCE_ENGINEERING, "is_graduate_school": True, "ranking_national": 14, "website": "https://www.buaa.edu.cn", "graduate_school_url": "https://yzb.buaa.edu.cn", "description": "航空航天领域的翘楚，计算机和软件工程实力强劲。"},

    # 211
    {"name": "北京邮电大学", "province": "北京", "city": "北京", "level": SchoolLevel.TWO_ONE_ONE, "school_type": SchoolType.SCIENCE_ENGINEERING, "is_graduate_school": True, "ranking_national": 40, "website": "https://www.bupt.edu.cn", "graduate_school_url": "https://yzb.bupt.edu.cn", "description": "信息通信领域的顶尖学府，计算机和通信专业就业极好。"},
    {"name": "上海财经大学", "province": "上海", "city": "上海", "level": SchoolLevel.TWO_ONE_ONE, "school_type": SchoolType.FINANCE_ECONOMICS, "is_graduate_school": True, "ranking_national": 45, "website": "https://www.sufe.edu.cn", "graduate_school_url": "https://gs.sufe.edu.cn", "description": "中国最好的财经类大学之一，金融和会计专业全国领先。"},
    {"name": "南京航空航天大学", "province": "江苏", "city": "南京", "level": SchoolLevel.TWO_ONE_ONE, "school_type": SchoolType.SCIENCE_ENGINEERING, "is_graduate_school": True, "ranking_national": 35, "website": "https://www.nuaa.edu.cn", "graduate_school_url": "https://www.graduate.nuaa.edu.cn", "description": "国防七子之一，航空航天和力学实力强。"},
    {"name": "西安电子科技大学", "province": "陕西", "city": "西安", "level": SchoolLevel.TWO_ONE_ONE, "school_type": SchoolType.SCIENCE_ENGINEERING, "is_graduate_school": True, "ranking_national": 38, "website": "https://www.xidian.edu.cn", "graduate_school_url": "https://yzb.xidian.edu.cn", "description": "电子信息领域的强校，通信和网络安全专业突出。"},

    # 双一流
    {"name": "中国科学院大学", "province": "北京", "city": "北京", "level": SchoolLevel.DOUBLE_FIRST_CLASS, "school_type": SchoolType.COMPREHENSIVE, "is_graduate_school": True, "ranking_national": 3, "website": "https://www.ucas.ac.cn", "graduate_school_url": "https://admission.ucas.ac.cn", "description": "中国科学院直属，以研究生教育为主，科研实力极强。"},
    {"name": "南方科技大学", "province": "广东", "city": "深圳", "level": SchoolLevel.DOUBLE_FIRST_CLASS, "school_type": SchoolType.SCIENCE_ENGINEERING, "is_graduate_school": True, "ranking_national": 25, "website": "https://www.sustech.edu.cn", "graduate_school_url": "https://gs.sustech.edu.cn", "description": "新兴研究型大学，国际化程度高，科研经费充足。"},
]

# 初始专业数据（常见考研专业）
INITIAL_MAJORS = [
    {"code": "081200", "name": "计算机科学与技术", "category": "工学", "first_level": "计算机科学与技术", "degree_level": DegreeLevel.MASTER, "exam_subjects": '["思想政治理论", "英语一", "数学一", "计算机专业基础综合"]', "description": "研究计算机系统结构、软件与理论、应用技术的学科。"},
    {"code": "083500", "name": "软件工程", "category": "工学", "first_level": "软件工程", "degree_level": DegreeLevel.MASTER, "exam_subjects": '["思想政治理论", "英语一", "数学一", "软件工程专业基础"]', "description": "研究软件开发和维护的工程化方法。"},
    {"code": "081000", "name": "信息与通信工程", "category": "工学", "first_level": "信息与通信工程", "degree_level": DegreeLevel.MASTER, "exam_subjects": '["思想政治理论", "英语一", "数学一", "通信原理"]', "description": "研究信息的获取、传输、处理和利用。"},
    {"code": "120200", "name": "工商管理", "category": "管理学", "first_level": "工商管理", "degree_level": DegreeLevel.MASTER, "exam_subjects": '["思想政治理论", "英语一", "数学三", "管理学"]', "description": "研究企业管理和市场经济规律的学科。"},
    {"code": "020204", "name": "金融学", "category": "经济学", "first_level": "应用经济学", "degree_level": DegreeLevel.MASTER, "exam_subjects": '["思想政治理论", "英语一", "数学三", "经济学综合"]', "description": "研究金融市场的运行机制和金融工具定价。"},
    {"code": "030100", "name": "法学", "category": "法学", "first_level": "法学", "degree_level": DegreeLevel.MASTER, "exam_subjects": '["思想政治理论", "英语一", "法硕联考专业基础", "法硕联考综合"]', "description": "研究法律理论和法律实践的应用学科。"},
    {"code": "100200", "name": "临床医学", "category": "医学", "first_level": "临床医学", "degree_level": DegreeLevel.MASTER, "exam_subjects": '["思想政治理论", "英语一", "临床医学综合"]', "description": "研究疾病的诊断、治疗和预防。"},
    {"code": "070100", "name": "数学", "category": "理学", "first_level": "数学", "degree_level": DegreeLevel.MASTER, "exam_subjects": '["思想政治理论", "英语一", "数学分析", "高等代数"]', "description": "研究数量、结构、变化和空间等概念。"},
]

# 历年国家线（学术学位，A类考生）
NATIONAL_LINES = [
    # (year, category, total, politics, english, biz1, biz2)
    (2021, "工学", 263, 37, 37, 56, 56),
    (2022, "工学", 273, 38, 38, 57, 57),
    (2023, "工学", 273, 38, 38, 57, 57),
    (2024, "工学", 273, 37, 37, 56, 56),
    (2025, "工学", 260, 34, 34, 51, 51),
    (2021, "经济学", 348, 49, 49, 74, 74),
    (2022, "经济学", 360, 52, 52, 78, 78),
    (2023, "经济学", 346, 48, 48, 72, 72),
    (2024, "经济学", 338, 47, 47, 71, 71),
    (2025, "经济学", 323, 40, 40, 60, 60),
    (2021, "管理学", 341, 48, 48, 72, 72),
    (2022, "管理学", 353, 51, 51, 77, 77),
    (2023, "管理学", 340, 47, 47, 71, 71),
    (2024, "管理学", 347, 49, 49, 74, 74),
    (2025, "管理学", 333, 40, 40, 60, 60),
    (2021, "法学", 321, 44, 44, 66, 66),
    (2022, "法学", 335, 46, 46, 69, 69),
    (2023, "法学", 326, 45, 45, 68, 68),
    (2024, "法学", 331, 47, 47, 71, 71),
    (2025, "法学", 323, 40, 40, 60, 60),
    (2021, "理学", 280, 37, 37, 56, 56),
    (2022, "理学", 290, 39, 39, 59, 59),
    (2023, "理学", 279, 38, 38, 57, 57),
    (2024, "理学", 288, 41, 41, 62, 62),
    (2025, "理学", 274, 35, 35, 53, 53),
]


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # 检查是否已有数据
        existing = db.query(School).count()
        if existing > 0:
            print(f"数据库已有 {existing} 所院校，跳过种子数据导入。")
            return

        # 导入院校
        print("导入院校数据...")
        for s in INITIAL_SCHOOLS:
            db.add(School(**s))
        db.commit()

        schools = db.query(School).all()
        print(f"已导入 {len(schools)} 所院校")

        # 导入专业（每个院校导入前几个专业）
        print("导入专业数据...")
        for school in schools:
            for m in INITIAL_MAJORS[:4]:  # 每个学校添加前4个常见专业
                major_data = {**m, "school_id": school.id}
                db.add(Major(**major_data))
        db.commit()
        print(f"已导入专业数据")

        # 导入国家线（不关联具体院校）
        print("导入国家线数据...")
        for nl in NATIONAL_LINES:
            year, cat, total, politics, english, biz1, biz2 = nl
            db.add(ScoreLine(
                school_id=0,
                major_code="",
                year=year,
                category="学硕",
                total_score=total,
                politics_score=politics,
                english_score=english,
                business_score_1=biz1,
                business_score_2=biz2,
                is_national_line=True,
            ))
        db.commit()
        print(f"已导入 {len(NATIONAL_LINES)} 条国家线数据")

        # 为一些知名院校生成模拟院校线（略高于国家线）
        print("生成模拟院校线...")
        top_schools = [s for s in schools if s.level in (SchoolLevel.C9, SchoolLevel.NINE_EIGHT_FIVE)]
        majors = db.query(Major).filter(Major.category == "工学").limit(3).all()

        for school in top_schools[:5]:
            for major in majors:
                base_offset = {"C9": 50, "985": 35}[school.level.value] if school.level.value in ("C9", "985") else 20
                for nl in NATIONAL_LINES:
                    year, cat, total, politics, english, biz1, biz2 = nl
                    if cat == "工学" and year >= 2021:
                        offset = base_offset + (year - 2021) * 3
                        db.add(ScoreLine(
                            school_id=school.id,
                            major_code=major.code,
                            year=year,
                            category="学硕",
                            total_score=total + offset,
                            politics_score=politics + 10,
                            english_score=english + 10,
                            business_score_1=biz1 + 25,
                            business_score_2=biz2 + 25,
                            applicant_count=200 + (year - 2021) * 30,
                            admit_count=20 + (year - 2021) * 2,
                            is_national_line=False,
                        ))
        db.commit()
        print("模拟院校线数据导入完成")

        print("\n=== 种子数据导入完毕 ===")
        print(f"院校: {db.query(School).count()} 所")
        print(f"专业: {db.query(Major).count()} 个")
        print(f"分数线: {db.query(ScoreLine).count()} 条")

    except Exception as e:
        db.rollback()
        print(f"导入失败: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
