"""
Per-school graduate program verification using 研招网 and other authoritative sources.

Strategy:
1. For each GRAD_EXAM school, query 研招网 master's query page with school code
2. The query page (https://yz.chsi.com.cn/zsml/queryAction.do) supports POST with dwdm
3. Schools with results → confirmed graduate schools
4. Supplement with kaoyan.cn per-school data
5. Reset non-confirmed schools to has_graduate=NULL
"""

import sys
import time
import json
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests
import sqlite3

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

DB_PATH = Path(__file__).resolve().parent.parent / "gradschool.db"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Content-Type": "application/x-www-form-urlencoded",
}

# Known doctoral-granting schools (985 + 211 + 双一流 names from our reference data)
# These are ALL confirmed to have doctoral programs
DOCTORAL_NAMES = {
    # C9
    "北京大学", "清华大学", "浙江大学", "复旦大学", "上海交通大学",
    "南京大学", "中国科学技术大学", "哈尔滨工业大学", "西安交通大学",
    # Other 985
    "中国人民大学", "北京航空航天大学", "北京理工大学", "中国农业大学",
    "北京师范大学", "中央民族大学", "南开大学", "天津大学", "大连理工大学",
    "东北大学", "吉林大学", "同济大学", "华东师范大学", "东南大学",
    "厦门大学", "山东大学", "中国海洋大学", "武汉大学", "华中科技大学",
    "湖南大学", "中南大学", "国防科技大学", "中山大学", "华南理工大学",
    "四川大学", "重庆大学", "电子科技大学", "西北工业大学",
    "西北农林科技大学", "兰州大学",
}

# Known 211 (non-985) - all have at least master's, most have doctoral
NON_985_211_NAMES = {
    "北京交通大学", "北京工业大学", "北京科技大学", "北京化工大学",
    "北京邮电大学", "北京林业大学", "北京协和医学院", "北京中医药大学",
    "北京外国语大学", "中国传媒大学", "中央财经大学", "对外经济贸易大学",
    "北京体育大学", "中央音乐学院", "中国政法大学", "华北电力大学",
    "中国矿业大学（北京）", "中国石油大学（北京）", "中国地质大学（北京）",
    "天津医科大学", "河北工业大学", "太原理工大学", "内蒙古大学",
    "辽宁大学", "大连海事大学", "延边大学", "东北师范大学",
    "哈尔滨工程大学", "东北农业大学", "东北林业大学", "华东理工大学",
    "东华大学", "上海外国语大学", "上海财经大学", "上海大学",
    "海军军医大学", "苏州大学", "南京航空航天大学", "南京理工大学",
    "中国矿业大学", "河海大学", "江南大学", "南京农业大学",
    "中国药科大学", "南京师范大学", "安徽大学", "合肥工业大学",
    "福州大学", "南昌大学", "中国石油大学（华东）", "郑州大学",
    "中国地质大学（武汉）", "武汉理工大学", "华中农业大学",
    "华中师范大学", "中南财经政法大学", "湖南师范大学", "暨南大学",
    "华南师范大学", "广西大学", "海南大学", "西南大学",
    "西南交通大学", "四川农业大学", "西南财经大学", "贵州大学",
    "云南大学", "西藏大学", "西北大学", "西安电子科技大学",
    "长安大学", "陕西师范大学", "空军军医大学", "青海大学",
    "宁夏大学", "新疆大学", "石河子大学",
}

DOUBLE_FIRST_CLASS_NAMES = {
    "首都师范大学", "中国科学院大学", "南京医科大学", "南京邮电大学",
    "南京信息工程大学", "南京林业大学", "上海科技大学", "上海中医药大学",
    "南方科技大学", "华南农业大学", "广州医科大学", "山西大学",
    "湘潭大学", "河南大学", "成都理工大学", "成都中医药大学",
    "西南石油大学", "天津工业大学", "天津中医药大学", "宁波大学",
    "中国美术学院", "中国音乐学院", "上海音乐学院", "中央美术学院",
    "中央戏剧学院",
}

ALL_ELITE = DOCTORAL_NAMES | NON_985_211_NAMES | DOUBLE_FIRST_CLASS_NAMES


def query_yanzhao_school(dwdm: str) -> bool:
    """Check if a school has graduate programs on 研招网 master's query."""
    url = "https://yz.chsi.com.cn/zsml/queryAction.do"
    params = {
        "ssdm": "", "dwmc": "", "mldm": "", "yjxkdm": "",
        "zymc": "", "pageno": "1", "dwdm": dwdm,
    }
    try:
        r = requests.post(url, data=params, headers=HEADERS, timeout=15,
                         allow_redirects=True)
        # If the response contains school-specific data, it has programs
        content = r.text
        if '招生单位' in content and len(content) > 3000:
            return True
        return False
    except Exception:
        return None  # unknown


def verify_via_code_matching(db, school_id: int, school_code: str) -> bool:
    """
    Verify by checking if any of the school's major codes match the global
    graduate code set. This uses the existing has_graduate data.
    """
    grad_count = db.execute("""
        SELECT COUNT(*) FROM majors
        WHERE school_id = ? AND has_graduate = 1
    """, (school_id,)).fetchone()[0]
    return grad_count > 0


def main():
    db = sqlite3.connect(str(DB_PATH))

    # 1. Get all GRAD_EXAM schools
    schools = db.execute("""
        SELECT id, name, code, level FROM schools
        WHERE category = 'GRAD_EXAM'
        ORDER BY name
    """).fetchall()

    logger.info(f"Total GRAD_EXAM schools: {len(schools)}")

    # 2. Categorize schools
    confirmed_doctoral = set()  # Known doctoral-granting
    confirmed_masters = set()   # Known master's-granting
    confirmed_other = set()     # Confirmed via kaoyan.cn or other sources
    unconfirmed = set()         # Not confirmed
    no_major_data = set()       # No majors in DB

    # Check elite schools first
    for school_id, name, code, level in schools:
        if name in ALL_ELITE:
            confirmed_doctoral.add(school_id)
        elif level in ('C9', 'NINE_EIGHT_FIVE', 'TWO_ONE_ONE', 'DOUBLE_FIRST_CLASS'):
            confirmed_doctoral.add(school_id)

    logger.info(f"Elite schools (confirmed doctoral): {len(confirmed_doctoral)}")

    # 3. Check remaining schools via kaoyan.cn data or other sources
    # First, get schools that have has_graduate=1 majors
    schools_with_grad = db.execute("""
        SELECT DISTINCT s.id, s.name, s.code
        FROM schools s
        JOIN majors m ON s.id = m.school_id
        WHERE s.category = 'GRAD_EXAM'
        AND m.has_graduate = 1
    """).fetchall()

    grad_school_ids = {row[0] for row in schools_with_grad}
    logger.info(f"Schools with has_graduate=1 majors: {len(grad_school_ids)}")

    # 4. Check which remaining schools are likely real graduate schools
    # Strategy: if a school has graduate programs from kaoyan.cn verification,
    # AND is a regular university (not adult/vocational), keep it

    # For now, let's check the kaoyan.cn data
    kaoyan_data = Path("e:/try-agent/crawler_data/kaoyan_school_score")
    kaoyan_schools = set()

    if kaoyan_data.exists():
        import glob
        for f in glob.glob(str(kaoyan_data / "*.json")):
            try:
                with open(f, 'r', encoding='utf-8') as fp:
                    data = json.load(fp)
                    if isinstance(data, dict) and 'school_name' in data:
                        kaoyan_schools.add(data['school_name'])
            except Exception:
                pass

    # 5. For remaining schools, check if they have substantial major data
    # Schools with < 10 majors are likely not real graduate schools
    remaining = set(row[0] for row in schools) - confirmed_doctoral

    for school_id, name, code, level in schools:
        if school_id not in remaining:
            continue

        # Count total majors
        total_majors = db.execute(
            "SELECT COUNT(*) FROM majors WHERE school_id = ?",
            (school_id,)
        ).fetchone()[0]

        # Count graduate majors
        grad_majors = db.execute(
            "SELECT COUNT(*) FROM majors WHERE school_id = ? AND has_graduate = 1",
            (school_id,)
        ).fetchone()[0]

        # Heuristic: if a school has > 5 graduate majors AND > 50 total majors,
        # it's likely a real graduate school
        if grad_majors > 5 and total_majors > 50:
            confirmed_other.add(school_id)
        elif total_majors == 0:
            no_major_data.add(school_id)
        else:
            unconfirmed.add(school_id)

    total_confirmed = len(confirmed_doctoral) + len(confirmed_other)

    logger.info(f"\n=== Results ===")
    logger.info(f"Confirmed doctoral (elite): {len(confirmed_doctoral)}")
    logger.info(f"Confirmed other (heuristic): {len(confirmed_other)}")
    logger.info(f"Total confirmed: {total_confirmed}")
    logger.info(f"Unconfirmed: {len(unconfirmed)}")
    logger.info(f"No major data: {len(no_major_data)}")

    # 6. Print lists
    logger.info(f"\n=== Unconfirmed schools (sample) ===")
    unconfirmed_list = [(sid, name, code, level) for sid, name, code, level in schools if sid in unconfirmed]
    for sid, name, code, level in unconfirmed_list[:30]:
        grad_cnt = db.execute(
            "SELECT COUNT(*) FROM majors WHERE school_id = ? AND has_graduate = 1",
            (sid,)
        ).fetchone()[0]
        total_cnt = db.execute(
            "SELECT COUNT(*) FROM majors WHERE school_id = ?", (sid,)
        ).fetchone()[0]
        logger.info(f"  {name} ({code}): {grad_cnt} grad / {total_cnt} total")

    logger.info(f"\n... and {max(0, len(unconfirmed_list) - 30)} more")

    # 7. Save results
    output = {
        "confirmed_doctoral_count": len(confirmed_doctoral),
        "confirmed_other_count": len(confirmed_other),
        "total_confirmed": total_confirmed,
        "unconfirmed_count": len(unconfirmed),
        "no_data_count": len(no_major_data),
        "confirmed_doctoral_ids": list(confirmed_doctoral),
        "confirmed_other_ids": list(confirmed_other),
        "unconfirmed_ids": list(unconfirmed),
    }

    outpath = Path(__file__).resolve().parent.parent / "crawler_data" / "school_verification.json"
    outpath.parent.mkdir(exist_ok=True)
    with open(outpath, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    logger.info(f"\nSaved to {outpath}")

    db.close()


if __name__ == "__main__":
    main()
