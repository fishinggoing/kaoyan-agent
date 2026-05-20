# kaoyan_agent/seed_data.py
import sqlite3
from kaoyan_agent.db.schema import create_tables


def seed(conn: sqlite3.Connection):
    create_tables(conn)

    schools = [
        ("北京大学", "985", "北京", "北京", "综合"),
        ("清华大学", "985", "北京", "北京", "综合"),
        ("浙江大学", "985", "浙江", "杭州", "综合"),
        ("上海交通大学", "985", "上海", "上海", "综合"),
        ("南京大学", "985", "江苏", "南京", "综合"),
        ("华中科技大学", "985", "湖北", "武汉", "理工"),
        ("武汉大学", "985", "湖北", "武汉", "综合"),
        ("杭州电子科技大学", "双非", "浙江", "杭州", "理工"),
        ("南京邮电大学", "双非", "江苏", "南京", "理工"),
        ("深圳大学", "双非", "广东", "深圳", "综合"),
    ]

    majors_data = {
        "计算机科学与技术": {
            "浙大": "A+",
            "北大": "A+",
            "清华": "A+",
            "上交": "A",
            "南大": "A",
            "华科": "A",
            "武大": "A-",
            "杭电": "B+",
            "南邮": "B",
            "深大": "B",
        },
        "软件工程": {
            "浙大": "A+",
            "北大": "A",
            "清华": "A",
            "上交": "A-",
            "南大": "A",
            "华科": "B+",
            "武大": "B+",
            "杭电": "B",
            "南邮": "B-",
            "深大": "B-",
        },
        "电子信息": {
            "浙大": "A-",
            "清华": "A+",
            "上交": "A",
            "南大": "B+",
            "华科": "B+",
            "杭电": "B+",
            "南邮": "B+",
        },
    }

    scores_data = {
        ("计算机科学与技术", "北京大学", 2025): (380, 1500, 35, 0.65),
        ("计算机科学与技术", "浙江大学", 2025): (375, 1200, 45, 0.60),
        ("计算机科学与技术", "南京大学", 2025): (370, 900, 50, 0.55),
        ("计算机科学与技术", "杭州电子科技大学", 2025): (310, 600, 80, 0.20),
        ("计算机科学与技术", "南京邮电大学", 2025): (300, 500, 90, 0.15),
        ("计算机科学与技术", "深圳大学", 2025): (320, 700, 60, 0.25),
        ("计算机科学与技术", "上海交通大学", 2025): (385, 1300, 30, 0.70),
        ("计算机科学与技术", "华中科技大学", 2025): (360, 800, 55, 0.50),
        ("计算机科学与技术", "武汉大学", 2025): (355, 750, 50, 0.50),
        ("计算机科学与技术", "清华大学", 2025): (395, 1000, 20, 0.75),
        ("软件工程", "浙江大学", 2025): (365, 600, 40, 0.55),
        ("软件工程", "南京大学", 2025): (360, 500, 45, 0.50),
        ("软件工程", "上海交通大学", 2025): (370, 550, 35, 0.60),
        ("软件工程", "华中科技大学", 2025): (345, 400, 50, 0.45),
        ("软件工程", "武汉大学", 2025): (340, 380, 48, 0.45),
        ("电子信息", "浙江大学", 2025): (355, 700, 50, 0.50),
        ("电子信息", "南京大学", 2025): (350, 500, 45, 0.45),
        ("电子信息", "上海交通大学", 2025): (365, 600, 35, 0.55),
        ("电子信息", "杭州电子科技大学", 2025): (290, 450, 100, 0.15),
        ("电子信息", "南京邮电大学", 2025): (285, 400, 90, 0.10),
        ("电子信息", "华中科技大学", 2025): (340, 450, 60, 0.40),
        ("电子信息", "清华大学", 2025): (390, 500, 25, 0.70),
    }

    employment_data = {
        "北京大学": (0.98, 280000, "北大毕业生广泛分布于各大互联网公司和金融机构"),
        "清华大学": (0.99, 300000, "清华计算机毕业生起薪极高，多进入头部企业和出国深造"),
        "浙江大学": (0.98, 250000, "浙江大学计算机就业集中在杭州互联网企业，阿里系公司为主要去向"),
        "上海交通大学": (0.97, 260000, "上交毕业生多去上海互联网/金融企业"),
        "南京大学": (0.97, 240000, "南京大学毕业生多去上海/南京互联网企业"),
        "华中科技大学": (0.95, 200000, "华科毕业生在深圳/武汉互联网企业就业率较高"),
        "武汉大学": (0.94, 190000, "武大毕业生广泛分布在中部和东部地区"),
        "杭州电子科技大学": (0.92, 150000, "杭电毕业生在杭州互联网企业认可度高，性价比好"),
        "南京邮电大学": (0.91, 140000, "南邮毕业生在通信/互联网行业就业稳定"),
        "深圳大学": (0.93, 180000, "深大毕业生在深圳互联网企业就业有地域优势"),
    }

    school_ids = {}
    for s in schools:
        conn.execute(
            "INSERT INTO schools (name, tier, province, city, type) VALUES (?,?,?,?,?)",
            s,
        )
        school_ids[s[0]] = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    major_ids = {}
    for major_name, school_ranks in majors_data.items():
        short_name_map = {
            "浙大": "浙江大学",
            "北大": "北京大学",
            "清华": "清华大学",
            "上交": "上海交通大学",
            "南大": "南京大学",
            "华科": "华中科技大学",
            "武大": "武汉大学",
            "杭电": "杭州电子科技大学",
            "南邮": "南京邮电大学",
            "深大": "深圳大学",
        }
        for short, rank in school_ranks.items():
            full_name = short_name_map[short]
            sid = school_ids[full_name]
            conn.execute(
                "INSERT INTO majors (school_id, name, discipline_rank, exam_subjects) VALUES (?,?,?,?)",
                (
                    sid,
                    major_name,
                    rank,
                    '["政治","英语","数学一","408"]',
                ),
            )
            major_ids[(major_name, full_name)] = conn.execute(
                "SELECT last_insert_rowid()"
            ).fetchone()[0]

    for (major_name, school_name, year), (
        line,
        applicants,
        enrolled,
        push_ratio,
    ) in scores_data.items():
        mid = major_ids[(major_name, school_name)]
        conn.execute(
            "INSERT INTO admission_scores (major_id, year, admission_line, applicants, enrolled, push_free_ratio) VALUES (?,?,?,?,?,?)",
            (mid, year, line, applicants, enrolled, push_ratio),
        )

    for school_name, (rate, salary, summary) in employment_data.items():
        sid = school_ids[school_name]
        conn.execute(
            "INSERT INTO employment_quality (school_id, year, employment_rate, avg_salary, summary) VALUES (?,?,?,?,?)",
            (sid, 2024, rate, salary, summary),
        )

    conn.commit()
    print(f"已导入 {len(schools)} 所学校的数据")


if __name__ == "__main__":
    conn = sqlite3.connect("kaoyan.db")
    conn.row_factory = sqlite3.Row
    seed(conn)
    conn.close()
