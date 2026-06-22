"""
Fetch all graduate major codes (zydm) from 研招网 public API and mark has_graduate.

No login required — queries by discipline category (mldm + yjxkdm) return
unique major codes without school attribution.

Usage:
  python -m scripts.fetch_yz_graduate_majors          # fetch + mark
  python -m scripts.fetch_yz_graduate_majors --dry-run  # fetch only, no DB update
"""

import sys
import time
import argparse
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests
from app.db.database import SessionLocal
from app.models import Major
from sqlalchemy import update

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Standard Chinese Graduate Discipline Catalog (2022 edition)
# mldm -> {yjxkdm: name}
GRADUATE_DISCIPLINES = {
    "01": {"0101": "哲学"},
    "02": {
        "0201": "理论经济学", "0202": "应用经济学",
    },
    "03": {
        "0301": "法学", "0302": "政治学", "0303": "社会学", "0304": "民族学",
        "0305": "马克思主义理论", "0306": "公安学", "0307": "中共党史党建学", "0308": "纪检监察学",
    },
    "04": {"0401": "教育学", "0402": "心理学", "0403": "体育学"},
    "05": {"0501": "中国语言文学", "0502": "外国语言文学", "0503": "新闻传播学"},
    "06": {"0601": "考古学", "0602": "中国史", "0603": "世界史"},
    "07": {
        "0701": "数学", "0702": "物理学", "0703": "化学", "0704": "天文学",
        "0705": "地理学", "0706": "大气科学", "0707": "海洋科学", "0708": "地球物理学",
        "0709": "地质学", "0710": "生物学", "0711": "系统科学", "0712": "科学技术史",
        "0713": "生态学", "0714": "统计学",
    },
    "08": {
        "0801": "力学", "0802": "机械工程", "0803": "光学工程",
        "0804": "仪器科学与技术", "0805": "材料科学与工程", "0806": "冶金工程",
        "0807": "动力工程及工程热物理", "0808": "电气工程", "0809": "电子科学与技术",
        "0810": "信息与通信工程", "0811": "控制科学与工程", "0812": "计算机科学与技术",
        "0813": "建筑学", "0814": "土木工程", "0815": "水利工程", "0816": "测绘科学与技术",
        "0817": "化学工程与技术", "0818": "地质资源与地质工程", "0819": "矿业工程",
        "0820": "石油与天然气工程", "0821": "纺织科学与工程", "0822": "轻工技术与工程",
        "0823": "交通运输工程", "0824": "船舶与海洋工程", "0825": "航空宇航科学与技术",
        "0826": "兵器科学与技术", "0827": "核科学与技术", "0828": "农业工程",
        "0829": "林业工程", "0830": "环境科学与工程", "0831": "生物医学工程",
        "0832": "食品科学与工程", "0833": "城乡规划学", "0834": "风景园林学",
        "0835": "软件工程", "0836": "生物工程", "0837": "安全科学与工程",
        "0838": "公安技术", "0839": "网络空间安全",
        "0854": "电子信息(专硕)", "0855": "机械(专硕)", "0856": "材料与化工(专硕)",
        "0857": "资源与环境(专硕)", "0858": "能源动力(专硕)", "0859": "土木水利(专硕)",
        "0860": "生物与医药(专硕)", "0861": "交通运输(专硕)", "0862": "风景园林(专硕)",
    },
    "09": {
        "0901": "作物学", "0902": "园艺学", "0903": "农业资源与环境",
        "0904": "植物保护", "0905": "畜牧学", "0906": "兽医学", "0907": "林学",
        "0908": "水产", "0909": "草学",
        "0951": "农业(专硕)", "0952": "兽医(专硕)", "0953": "风景园林(专硕)", "0954": "林业(专硕)",
    },
    "10": {
        "1001": "基础医学", "1002": "临床医学", "1003": "口腔医学",
        "1004": "公共卫生与预防医学", "1005": "中医学", "1006": "中西医结合",
        "1007": "药学", "1008": "中药学", "1009": "特种医学", "1010": "医学技术",
        "1011": "护理学",
        "1051": "临床医学(专硕)", "1052": "口腔医学(专硕)", "1053": "公共卫生(专硕)",
        "1054": "护理(专硕)", "1055": "药学(专硕)", "1056": "中药学(专硕)", "1057": "中医(专硕)",
    },
    "11": {
        "1101": "军事思想与军事历史", "1102": "战略学", "1103": "战役学",
        "1104": "战术学", "1105": "军队指挥学", "1106": "军制学", "1107": "军队政治工作学",
        "1108": "军事后勤学", "1109": "军事装备学", "1110": "军事训练学",
    },
    "12": {
        "1201": "管理科学与工程", "1202": "工商管理", "1203": "农林经济管理",
        "1204": "公共管理", "1205": "图书情报与档案管理",
        "1251": "工商管理(专硕)", "1252": "公共管理(专硕)", "1253": "会计(专硕)",
        "1254": "旅游管理(专硕)", "1255": "图书情报(专硕)", "1256": "工程管理(专硕)",
    },
    "13": {
        "1301": "艺术学理论",
        "1352": "音乐(专硕)", "1353": "舞蹈(专硕)", "1354": "戏剧与影视(专硕)",
        "1355": "美术与书法(专硕)", "1356": "艺术设计(专硕)",
    },
    "14": {
        "1401": "集成电路科学与工程", "1402": "国家安全学", "1403": "设计学",
        "1404": "遥感科学与技术", "1405": "智能科学与技术", "1406": "纳米科学与工程",
        "1407": "区域国别学",
    },
    # 专业学位: use zyxw as mldm with yjxkdm = zyxw
    "zyxw": {"zyxw": "专业学位"},
}

YANZHAO_API = "https://yz.chsi.com.cn/zsml/rs/zys.do"
REQUEST_DELAY = 0.5  # polite delay between requests
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "X-Requested-With": "XMLHttpRequest",
    "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
}


def fetch_all_graduate_codes() -> set[str]:
    """Fetch all unique zydm (graduate major codes) from 研招网 public API."""
    all_zydm = set()
    total_disciplines = sum(len(v) for v in GRADUATE_DISCIPLINES.values())

    i = 0
    for mldm, disciplines in GRADUATE_DISCIPLINES.items():
        for yjxkdm, name in disciplines.items():
            i += 1
            logger.info(f"[{i}/{total_disciplines}] {mldm}/{yjxkdm} {name}")

            page = 1
            discipline_zydm = set()

            while True:
                try:
                    params = {"pageno": str(page)}
                    # For zyxw (专业学位), only use yjxkdm
                    if mldm == "zyxw":
                        params["yjxkdm"] = "zyxw"
                    else:
                        params["mldm"] = mldm
                        params["yjxkdm"] = yjxkdm

                    r = requests.post(YANZHAO_API, data=params, headers=HEADERS, timeout=30)
                    data = r.json()
                    msg = data.get("msg", {})

                    if not isinstance(msg, dict):
                        logger.warning(f"  Unexpected response: {str(msg)[:100]}")
                        break

                    items = msg.get("list", [])
                    total_count = msg.get("totalCount", 0)
                    total_page = msg.get("totalPage", 0)

                    for item in items:
                        zydm = item.get("zydm", "")
                        if zydm:
                            discipline_zydm.add(zydm)

                    if page >= total_page:
                        break

                    page += 1
                    time.sleep(REQUEST_DELAY)

                except Exception as e:
                    logger.error(f"  Error on page {page}: {e}")
                    time.sleep(2)  # back off on error
                    page += 1
                    if page > 30:  # safety limit
                        break

            logger.info(f"  -> {len(discipline_zydm)} unique zydm from {total_count} entries")
            all_zydm.update(discipline_zydm)
            time.sleep(REQUEST_DELAY)

    return all_zydm


def mark_graduate_majors(zydm_set: set[str], dry_run: bool = False):
    """Mark majors in database as has_graduate=True where code matches."""
    db = SessionLocal()
    try:
        # Count matching majors before update
        from sqlalchemy import select, func
        total_majors = db.execute(select(func.count()).select_from(Major)).scalar()
        matching = db.execute(
            select(func.count()).select_from(Major).where(Major.code.in_(zydm_set))
        ).scalar()

        logger.info(f"Database: {total_majors} total majors, {matching} match graduate codes")

        if dry_run:
            logger.info("DRY RUN — no changes made")
            # Show which codes matched
            matched_codes = list(db.execute(
                select(Major.code, func.count())
                .where(Major.code.in_(zydm_set))
                .group_by(Major.code)
                .order_by(Major.code)
            ).all())
            logger.info(f"Matched {len(matched_codes)} unique codes:")
            for code, count in matched_codes:
                logger.info(f"  {code}: {count} majors")
            return

        # Reset all to NULL first, then mark confirmed
        db.execute(update(Major).values(has_graduate=None))
        db.execute(
            update(Major)
            .where(Major.code.in_(zydm_set))
            .values(has_graduate=True)
        )
        db.commit()
        logger.info(f"Marked {matching} majors as has_graduate=True")

        # Stats
        confirmed = db.execute(
            select(func.count()).select_from(Major).where(Major.has_graduate == True)
        ).scalar()
        unknown = db.execute(
            select(func.count()).select_from(Major).where(Major.has_graduate == None)
        ).scalar()
        logger.info(f"Final: {confirmed} confirmed, {unknown} unknown, 0 false")

    finally:
        db.close()


def main():
    global REQUEST_DELAY
    parser = argparse.ArgumentParser(description="Fetch graduate major codes from 研招网")
    parser.add_argument("--dry-run", action="store_true", help="Fetch only, don't update DB")
    parser.add_argument("--delay", type=float, default=REQUEST_DELAY, help="Delay between requests")
    args = parser.parse_args()
    REQUEST_DELAY = args.delay

    logger.info("Fetching graduate major codes from 研招网...")
    zydm_set = fetch_all_graduate_codes()
    logger.info(f"Total unique graduate major codes: {len(zydm_set)}")

    mark_graduate_majors(zydm_set, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
