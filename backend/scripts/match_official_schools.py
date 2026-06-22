"""
Match OCR-extracted school names from gxzsxx.net against the database,
then reset has_graduate for schools NOT on the official list.

Usage:
  python scripts/match_official_schools.py           # match + report
  python scripts/match_official_schools.py --execute  # match + update DB
"""

import json
import re
import sys
import logging
from pathlib import Path
from difflib import SequenceMatcher

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import sqlite3

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

DB_PATH = Path(__file__).resolve().parent.parent / "gradschool.db"
OCR_DATA = Path("e:/try-agent/crawler_data/official_869_schools.json")

# Department suffixes commonly appended by OCR
DEPT_SUFFIXES = [
    '教育部', '工信部', '国家民委', '国家卫健委', '公安部', '外交部',
    '交通运输部', '国家体育总局', '中国科学院', '中国社会科学院',
    '财政部', '水利部', '农业农村部', '生态环境部', '应急管理部',
    '司法部', '科学技术部', '文化和旅游部', '退役军人事务部',
    '国家中医药管理局', '国家国防科工局', '海关总署',
    '中央统战部', '中央办公厅', '国务院侨办',
    '民用航空局', '国家铁路局', '国家邮政局',
    '中国地震局', '中国气象局', '国家海洋局',
    '中华全国总工会', '共青团中央', '全国妇联',
    '北京市', '天津市', '上海市', '重庆市',
    '河北省', '山西省', '内蒙古自治区', '辽宁省', '吉林省', '黑龙江省',
    '江苏省', '浙江省', '安徽省', '福建省', '江西省', '山东省',
    '河南省', '湖北省', '湖南省',
    '广东省', '广西壮族自治区', '海南省',
    '四川省', '贵州省', '云南省', '西藏自治区',
    '陕西省', '甘肃省', '青海省', '宁夏回族自治区', '新疆维吾尔自治区',
    '天津市天', '河北省天', '山西省天', '辽宁省天',
]


def clean_school_name(raw_name: str) -> str:
    """Strip department/province suffixes from OCR school name."""
    name = raw_name.strip()

    # Remove parentheses artifacts like 《北京7, 北京), 《北京》
    name = re.sub(r'[《〈]\s*北京\s*\d*\s*[》〉)\]]?\s*', '', name)
    name = re.sub(r'[《〈]\s*[^》〉)]*[》〉)]', '', name)
    name = re.sub(r'\s*\(\s*北京\s*\)', '', name)
    name = re.sub(r'\s*（\s*北京\s*）', '', name)

    # Remove common OCR noise at end: single chars, numbers, symbols
    name = re.sub(r'[\s\|｜\-\—·]+$', '', name)
    name = re.sub(r'[天0-9]{1,2}\s*$', '', name)

    # Try removing known dept/province suffixes
    for suffix in sorted(DEPT_SUFFIXES, key=len, reverse=True):
        if name.endswith(suffix) and len(name) > len(suffix) + 2:
            name = name[:-len(suffix)]
            break

    # Remove trailing location markers (省, 市, 区, 县)
    while name and len(name) > 4:
        stripped = False
        for suffix in ['自治区', '自治州', '地区', '省', '市', '区', '县', '盟']:
            if name.endswith(suffix) and not name.endswith('自治区') == False and len(name) - len(suffix) >= 4:
                name = name[:-len(suffix)]
                stripped = True
                break
        if not stripped:
            break

    # Remove trailing junk characters
    name = re.sub(r'[\s\d\|｜\.\,，,。\.、;；:：!！?？\-—·]+$', '', name)
    name = name.strip()

    # Fix common OCR errors
    fixes = {
        '北奈大学': '北京大学',
        '北京叶子科技学院': '北京电子科技学院',
        '北京迟电科技大学': '北京信息科技大学',
        '河北病范大学': '河北师范大学',
        '山西病范大学': '山西师范大学',
        '天持大学': '天津大学',
    }
    name = fixes.get(name, name)

    return name.strip()


def similarity(a: str, b: str) -> float:
    """Calculate string similarity score."""
    return SequenceMatcher(None, a, b).ratio()


def match_schools():
    """Match OCR school names to database schools."""
    # Load OCR data
    with open(OCR_DATA, 'r', encoding='utf-8') as f:
        ocr_data = json.load(f)

    db = sqlite3.connect(str(DB_PATH))

    # Get all GRAD_EXAM schools
    db_schools = db.execute("""
        SELECT id, name, level FROM schools
        WHERE category = 'GRAD_EXAM'
        ORDER BY name
    """).fetchall()

    logger.info(f"Database GRAD_EXAM schools: {len(db_schools)}")
    logger.info(f"OCR doctoral schools: {ocr_data['doctoral_count']}")
    logger.info(f"OCR masters schools: {ocr_data['masters_count']}")
    logger.info(f"OCR total: {ocr_data['count']}")

    # Build lookup maps
    db_names = {row[1]: (row[0], row[2]) for row in db_schools}

    # Match each OCR school
    matched_ids = set()
    matched_doctoral = set()
    matched_masters = set()
    unmatched = []
    fuzzy_matches = []

    all_ocr_schools = [
        (name, 'doctoral') for name in ocr_data['doctoral']
    ] + [
        (name, 'masters') for name in ocr_data['masters']
    ]

    for raw_name, category in all_ocr_schools:
        clean_name = clean_school_name(raw_name)

        # Try exact match first
        if clean_name in db_names:
            sid = db_names[clean_name][0]
            matched_ids.add(sid)
            if category == 'doctoral':
                matched_doctoral.add(sid)
            else:
                matched_masters.add(sid)
            continue

        # Try exact match with raw name
        if raw_name in db_names:
            sid = db_names[raw_name][0]
            matched_ids.add(sid)
            if category == 'doctoral':
                matched_doctoral.add(sid)
            else:
                matched_masters.add(sid)
            continue

        # Try fuzzy match
        best_score = 0
        best_match = None
        for db_name, (sid, level) in db_names.items():
            # Skip already matched schools
            if sid in matched_ids:
                continue
            score = similarity(clean_name, db_name)
            if score > best_score and score > 0.85:
                best_score = score
                best_match = (sid, db_name, level)
            # Also try matching by dropping dept suffixes from DB name
            score2 = similarity(clean_name, db_name[:len(clean_name)])
            if score2 > best_score and score2 > 0.85:
                best_score = score2
                best_match = (sid, db_name, level)

        if best_match and best_score > 0.85:
            matched_ids.add(best_match[0])
            if category == 'doctoral':
                matched_doctoral.add(best_match[0])
            else:
                matched_masters.add(best_match[0])
            fuzzy_matches.append((clean_name, best_match[1], best_score))
        else:
            unmatched.append((clean_name, raw_name, category))

    # Report
    logger.info(f"\n{'=' * 60}")
    logger.info(f"MATCHING RESULTS")
    logger.info(f"{'=' * 60}")
    logger.info(f"Exact matches: {len(matched_ids) - len(fuzzy_matches)}")
    logger.info(f"Fuzzy matches: {len(fuzzy_matches)}")
    logger.info(f"Total matched: {len(matched_ids)}")
    logger.info(f"  Doctoral: {len(matched_doctoral)}")
    logger.info(f"  Masters: {len(matched_masters)}")
    logger.info(f"Unmatched: {len(unmatched)}")

    if fuzzy_matches:
        logger.info(f"\n--- Fuzzy Matches (top 20) ---")
        for clean, db_name, score in fuzzy_matches[:20]:
            logger.info(f"  {clean} -> {db_name} ({score:.2f})")

    if unmatched:
        logger.info(f"\n--- Unmatched OCR Schools ({len(unmatched)}) ---")
        for clean, raw, cat in unmatched:
            logger.info(f"  [{cat}] {clean} (raw: {raw})")

    # Save results
    result = {
        'matched_count': len(matched_ids),
        'doctoral_matched': len(matched_doctoral),
        'masters_matched': len(matched_masters),
        'unmatched_count': len(unmatched),
        'matched_ids': list(matched_ids),
        'unmatched': [{'clean': c, 'raw': r, 'category': cat} for c, r, cat in unmatched],
        'fuzzy_matches': [{'ocr': c, 'db': d, 'score': s} for c, d, s in fuzzy_matches],
    }

    outpath = Path("e:/try-agent/crawler_data/school_match_results.json")
    with open(outpath, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    logger.info(f"\nSaved match results to {outpath}")

    db.close()
    return matched_ids, unmatched


def update_database(matched_ids: set[int]):
    """Reset has_graduate to NULL for schools not in the official list."""
    db = sqlite3.connect(str(DB_PATH))

    # Count before
    before_grad = db.execute(
        "SELECT COUNT(DISTINCT school_id) FROM majors WHERE has_graduate = 1"
    ).fetchone()[0]
    before_majors = db.execute(
        "SELECT COUNT(*) FROM majors WHERE has_graduate = 1"
    ).fetchone()[0]

    # Get school IDs that are GRAD_EXAM but NOT in matched list
    grad_schools = db.execute(
        "SELECT id FROM schools WHERE category = 'GRAD_EXAM'"
    ).fetchall()
    grad_ids = {row[0] for row in grad_schools}

    to_null = grad_ids - matched_ids
    logger.info(f"Schools to set NULL: {len(to_null)}")

    if to_null:
        placeholders = ','.join('?' * len(to_null))

        # First, NULL out schools not in official list
        db.execute(f"""
            UPDATE majors SET has_graduate = NULL
            WHERE school_id IN ({placeholders})
            AND has_graduate = 1
        """, list(to_null))

        # Also NULL out non-GRAD_EXAM schools (safety cleanup)
        db.execute("""
            UPDATE majors SET has_graduate = NULL
            WHERE school_id IN (SELECT id FROM schools WHERE category != 'GRAD_EXAM')
            AND has_graduate = 1
        """)

        db.commit()

    # Count after
    after_grad = db.execute(
        "SELECT COUNT(DISTINCT school_id) FROM majors WHERE has_graduate = 1"
    ).fetchone()[0]
    after_majors = db.execute(
        "SELECT COUNT(*) FROM majors WHERE has_graduate = 1"
    ).fetchone()[0]

    logger.info(f"\n{'=' * 60}")
    logger.info(f"DATABASE UPDATE RESULTS")
    logger.info(f"{'=' * 60}")
    logger.info(f"Before: {before_grad} schools, {before_majors} majors")
    logger.info(f"After:  {after_grad} schools, {after_majors} majors")
    logger.info(f"Removed: {before_grad - after_grad} schools, {before_majors - after_majors} majors")

    # Verify: check a few 985 schools
    logger.info(f"\n--- 985 School Verification ---")
    for name in ['北京大学', '清华大学', '浙江大学', '哈尔滨工业大学']:
        row = db.execute("""
            SELECT COUNT(*) FROM majors m
            JOIN schools s ON m.school_id = s.id
            WHERE s.name = ? AND m.has_graduate = 1
        """, (name,)).fetchone()
        logger.info(f"  {name}: {row[0]} graduate majors")

    # Check some random remaining GRAD_EXAM schools
    logger.info(f"\n--- Remaining Schools with has_graduate=1 (sample) ---")
    sample = db.execute("""
        SELECT s.name, COUNT(m.id) as cnt
        FROM schools s
        JOIN majors m ON s.id = m.school_id
        WHERE m.has_graduate = 1
        GROUP BY s.id
        ORDER BY s.name
        LIMIT 20
    """).fetchall()
    for name, cnt in sample:
        logger.info(f"  {name}: {cnt}")

    db.commit()
    db.close()


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--execute', action='store_true', help='Update database')
    args = parser.parse_args()

    matched_ids, unmatched = match_schools()

    if args.execute:
        update_database(matched_ids)
        logger.info("\nDatabase updated successfully!")
    else:
        logger.info("\nDry run — no database changes. Use --execute to apply.")


if __name__ == '__main__':
    main()
