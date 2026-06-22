"""
Final matching: Use longest-prefix-match against DB school names.
This handles OCR suffixes (provinces, departments, noise) robustly.

Strategy:
1. For each OCR school name, find the best matching DB school by:
   a. Exact match (after standard cleaning)
   b. Longest prefix match (OCR name starts with DB name)
   c. Fuzzy match (for OCR character errors)

2. The official 621 schools are the matched set.
3. Set has_graduate=NULL for all other GRAD_EXAM schools.
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


def normalize(name: str) -> str:
    """Basic normalization for comparison."""
    name = name.strip()
    # Remove parentheses and their content
    name = re.sub(r'[（({《〈].*?[）)}》〉]', '', name)
    # Remove common OCR noise
    name = re.sub(r'[\s\|｜\-—·\d]+', '', name)
    return name


# School renames: post-OCR-fix name → DB actual name
# (checked AFTER clean() has applied OCR character fixes)
SCHOOL_ALIASES = {
    '河北中医学院': '河北中医药大学',
    '吉林化工学院': '吉林化工大学',
    '牡丹江医学院': '牡丹江医科大学',
    '浙江科技学院': '浙江科技大学',
    '合肥学院': '合肥大学',
    '安徽科技学院': '安徽科技工程大学',
    '福建工程学院': '福建理工大学',
    '佛山科学技术学院': '佛山大学',
    '天水师范学院': '天水师范大学',
    '信阳师范学院': '信阳师范大学',
    '潍坊医学院': '山东第二医科大学',
    '桂林医学院': '桂林医科大学',
    '海南医学院': '海南医科大学',
    '皖南医学院': '皖南医科大学',
    '蚌埠医学院': '蚌埠医科大学',
    '赤峰学院': '赤峰大学',
    '嘉兴学院': '嘉兴大学',
    '西藏农牧学院': '西藏农牧大学',
    '湖南理工学院': '湖南理工大学',
    '重庆科技学院': '重庆科技大学',
    '重庆三峡学院': '重庆三峡科技大学',
    '宁夏师范学院': '宁夏师范大学',
    '湖州师范学院': '湖州师范大学',
    '新乡医学院': '河南医药大学',
    '淮阴工学院': '淮安大学',
    '山东第一医科大学': '泰山医学院',
}


def clean(raw: str) -> str:
    """Aggressively clean OCR name to extract just the school name."""
    name = raw.strip()

    # Fix common OCR character errors BEFORE cleaning
    # Longer/more-specific patterns first to avoid partial replacement issues
    ocr_fixes = {
        # Multi-char place name errors
        '险尔滨': '哈尔滨',
        '内蒙吉': '内蒙古',
        '了瑟西': '陕西',
        '移枝花': '攀枝花',
        '钟代': '仲恺',
        '争理': '伊犁',
        # 湖→various OCR garbling (湖 is the most frequently misread character)
        '潮南': '湖南',
        '潮北': '湖北',
        '调北': '湖北',
        '调南': '湖南',
        '调州': '湖州',
        '滑南': '湖南',
        '淹南': '湖南',
        # 成→various
        '茂都': '成都',
        '戒都': '成都',
        '忒都': '成都',
        # 武→臣
        '臣汉': '武汉',
        # 电→various
        '于力': '电力',
        '邮囊': '邮电',
        '邮时': '邮电',
        # 师→various
        '鲁范': '师范',
        '印范': '师范',
        '病范': '师范',
        # Character-level fixes
        '北奈': '北京',
        '天持': '天津',
        '黉华': '清华',
        '鼍': '电',
        '农明': '农垦',
        '曲齐': '曲阜',
        '重东': '重庆',
        '早南': '暨南',
        '农收': '农牧',
        '灾通': '交通',
        '其肃': '甘肃',
        '再年': '青年',
        '赤蜂': '赤峰',
        '济海': '渤海',
        '蒂山': '鞍山',
        '钵育': '体育',
        '豪兴': '嘉兴',
        '皇阳': '阜阳',
        '蚌塌': '蚌埠',
        '国江': '闽江',
        '永州师范': '泉州师范',
        '诸南师范': '赣南师范',
        '黄站': '黄冈',
        '擎庆': '肇庆',
        '三凿': '三峡',
        '四州警察': '四川警察',
        '了瑟': '陕',
        # Extra: common OCR suffixes from table noise
        '叶子科技': '电子科技',
        '迟电科技': '信息科技',
    }
    for wrong, right in ocr_fixes.items():
        name = name.replace(wrong, right)

    # Remove parenthesized content (OCR artifacts)
    name = re.sub(r'[（(][^）)]*[）)]', '', name)
    name = re.sub(r'[《〈][^》〉]*[》〉]', '', name)

    # Remove all whitespace, numbers, special chars
    name = re.sub(r'[\s\d\|｜\-—·,，.。、;；:：!！?？]+', '', name)

    return name.strip()


def match_schools():
    """Match OCR names to DB schools using prefix matching."""
    with open(OCR_DATA, 'r', encoding='utf-8') as f:
        ocr_data = json.load(f)

    db = sqlite3.connect(str(DB_PATH))

    # Get all GRAD_EXAM school names
    db_schools = db.execute("""
        SELECT id, name FROM schools WHERE category = 'GRAD_EXAM'
    """).fetchall()

    # Build index: normalized_name -> (id, original_name)
    db_index = {}
    for sid, name in db_schools:
        norm = normalize(name)
        if norm:
            db_index[norm] = (sid, name)
            # Also add variants
            db_index[name] = (sid, name)

    # Build list sorted by length (longest first) for prefix matching
    db_names_sorted = sorted(db_index.items(), key=lambda x: -len(x[0]))

    matched_ids = {}
    unmatched = []

    all_ocr = []
    for cat in ('doctoral', 'masters'):
        for name in ocr_data.get(cat, []):
            all_ocr.append((name, cat))

    for raw_ocr, cat in all_ocr:
        clean_name = clean(raw_ocr)

        if not clean_name or len(clean_name) < 4:
            unmatched.append((raw_ocr, cat, "too short"))
            continue

        matched = False

        # 1. Exact match (normalized)
        norm_ocr = normalize(raw_ocr)
        if norm_ocr in db_index:
            sid, db_name = db_index[norm_ocr]
            matched_ids[sid] = {'db_name': db_name, 'cat': cat, 'method': 'exact'}
            matched = True
            continue

        # 2. Try clean name exact match
        if clean_name in db_index:
            sid, db_name = db_index[clean_name]
            matched_ids[sid] = {'db_name': db_name, 'cat': cat, 'method': 'clean_exact'}
            matched = True
            continue

        # 2.5 Try alias lookup (renamed schools)
        # Check exact and prefix match because clean_name may have trailing province noise
        matched_alias = None
        for alias_key, alias_val in SCHOOL_ALIASES.items():
            if clean_name == alias_key or clean_name.startswith(alias_key):
                matched_alias = (alias_key, alias_val)
                break
        if matched_alias:
            alias_key, alias_val = matched_alias
            if alias_val in db_index:
                sid, db_name = db_index[alias_val]
                matched_ids[sid] = {'db_name': db_name, 'cat': cat, 'method': f'alias({alias_key}->{alias_val})'}
                matched = True
                continue
            alias_norm = normalize(alias_val)
            if alias_norm in db_index:
                sid, db_name = db_index[alias_norm]
                matched_ids[sid] = {'db_name': db_name, 'cat': cat, 'method': f'alias({alias_key}->{alias_val})'}
                matched = True
                continue

        # 3. Longest prefix match: OCR clean name starts with DB name
        best_len = 0
        best_match = None
        for db_norm, (sid, db_name) in db_names_sorted:
            if len(db_norm) >= 4 and clean_name.startswith(db_norm):
                if len(db_norm) > best_len:
                    best_len = len(db_norm)
                    best_match = (sid, db_name)
            # Also try: DB name starts with OCR
            if len(clean_name) >= 6 and db_norm.startswith(clean_name):
                if len(clean_name) > best_len:
                    best_len = len(clean_name)
                    best_match = (sid, db_name)

        if best_match and best_len >= 4:
            sid, db_name = best_match
            matched_ids[sid] = {'db_name': db_name, 'cat': cat, 'method': f'prefix({best_len})'}
            matched = True
            continue

        # 4. Fuzzy match for OCR errors (lower threshold to catch more)
        best_score = 0
        best_fuzzy = None
        for db_norm, (sid, db_name) in db_names_sorted:
            score = SequenceMatcher(None, clean_name[:len(db_norm)+5], db_norm).ratio()
            if score > best_score and score > 0.78:
                best_score = score
                best_fuzzy = (sid, db_name)
            # Also try matching first N chars
            if len(clean_name) >= 6 and len(db_norm) >= 6:
                n = min(len(clean_name), len(db_norm))
                score2 = SequenceMatcher(None, clean_name[:n], db_norm[:n]).ratio()
                if score2 > best_score and score2 > 0.85:
                    best_score = score2
                    best_fuzzy = (sid, db_name)

        if best_fuzzy and best_score > 0.78:
            sid, db_name = best_fuzzy
            matched_ids[sid] = {'db_name': db_name, 'cat': cat, 'method': f'fuzzy({best_score:.2f})'}
            matched = True
            continue

        if not matched:
            unmatched.append((raw_ocr, cat, clean_name))

    # Report
    doctoral_matched = sum(1 for v in matched_ids.values() if v['cat'] == 'doctoral')
    masters_matched = sum(1 for v in matched_ids.values() if v['cat'] == 'masters')

    logger.info(f"OCR: {len(all_ocr)} total ({len(ocr_data['doctoral'])} doctoral, {len(ocr_data['masters'])} masters)")
    logger.info(f"Matched: {len(matched_ids)} schools ({doctoral_matched} doctoral, {masters_matched} masters)")
    logger.info(f"Unmatched: {len(unmatched)}")

    if unmatched:
        logger.info(f"\n--- Unmatched ({len(unmatched)}) ---")
        for raw, cat, clean_name in unmatched[:30]:
            logger.info(f"  [{cat}] raw={raw}")
            logger.info(f"         clean={clean_name}")

    # Save
    outpath = Path("e:/try-agent/crawler_data/school_match_final.json")
    result = {
        'matched_count': len(matched_ids),
        'doctoral_matched': doctoral_matched,
        'masters_matched': masters_matched,
        'unmatched_count': len(unmatched),
        'matched_ids': list(matched_ids.keys()),
        'matched_details': {str(k): v for k, v in matched_ids.items()},
    }
    with open(outpath, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    logger.info(f"\nSaved to {outpath}")

    db.close()
    return matched_ids, unmatched


def update_db(matched_ids):
    """Reset has_graduate for non-official schools."""
    db = sqlite3.connect(str(DB_PATH))

    before_grad = db.execute(
        "SELECT COUNT(DISTINCT school_id) FROM majors WHERE has_graduate = 1"
    ).fetchone()[0]

    before_majors = db.execute(
        "SELECT COUNT(*) FROM majors WHERE has_graduate = 1"
    ).fetchone()[0]

    # Get all GRAD_EXAM school IDs
    all_grad_ids = {row[0] for row in db.execute(
        "SELECT id FROM schools WHERE category = 'GRAD_EXAM'"
    ).fetchall()}

    # Schools to keep (in official list)
    keep_ids = matched_ids.keys()

    # Schools to NULL out
    null_ids = all_grad_ids - keep_ids

    logger.info(f"GRAD_EXAM schools total: {len(all_grad_ids)}")
    logger.info(f"Schools to KEEP (official list): {len(keep_ids)}")
    logger.info(f"Schools to NULL: {len(null_ids)}")

    # Also NULL out non-GRAD_EXAM schools (safety)
    non_grad_ids = {row[0] for row in db.execute(
        "SELECT id FROM schools WHERE category != 'GRAD_EXAM'"
    ).fetchall()}

    all_null = null_ids | non_grad_ids

    # Batch update
    batch_size = 500
    null_list = list(all_null)
    for i in range(0, len(null_list), batch_size):
        batch = null_list[i:i+batch_size]
        placeholders = ','.join('?' * len(batch))
        db.execute(f"""
            UPDATE majors SET has_graduate = NULL
            WHERE school_id IN ({placeholders})
            AND has_graduate = 1
        """, batch)
    db.commit()

    after_grad = db.execute(
        "SELECT COUNT(DISTINCT school_id) FROM majors WHERE has_graduate = 1"
    ).fetchone()[0]
    after_majors = db.execute(
        "SELECT COUNT(*) FROM majors WHERE has_graduate = 1"
    ).fetchone()[0]

    logger.info(f"\nBefore: {before_grad} schools, {before_majors} majors")
    logger.info(f"After:  {after_grad} schools, {after_majors} majors")
    logger.info(f"Removed: {before_grad - after_grad} schools, {before_majors - after_majors} majors")

    # Verify key schools
    for name in ['北京大学', '清华大学', '浙江大学', '哈尔滨工业大学', '武汉大学']:
        row = db.execute("""
            SELECT COUNT(*) FROM majors m
            JOIN schools s ON m.school_id = s.id
            WHERE s.name = ? AND m.has_graduate = 1
        """, (name,)).fetchone()
        logger.info(f"  {name}: {row[0]} grad majors")

    db.close()


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()

    matched, unmatched = match_schools()

    if args.execute:
        update_db(matched)
        logger.info("\nDatabase updated!")
    else:
        logger.info("\nDry run. Use --execute to apply.")


if __name__ == '__main__':
    main()
