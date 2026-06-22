"""
OCR the gxzsxx.net images to extract the official 621-school list.
Uses tesseract with Chinese language support.
"""

import os
import re
import json
import sys
from pathlib import Path

os.environ['TESSDATA_PREFIX'] = os.path.expanduser('~/tessdata')

from PIL import Image
import numpy as np
import pytesseract

pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# Province names (bare names without 省/市 suffix, as OCR outputs them space-separated)
PROVINCE_NAMES = {
    '北京', '天津', '上海', '重庆',
    '辽宁', '吉林', '黑龙江',
    '河北', '山西', '内蒙古',
    '江苏', '浙江', '安徽', '福建', '江西', '山东',
    '河南', '湖北', '湖南',
    '广东', '广西', '海南',
    '四川', '贵州', '云南', '西藏',
    '陕西', '甘肃', '青海', '宁夏', '新疆',
    '香港', '澳门', '台湾',
}

# Department/ministry names that appear between school name and province
DEPARTMENT_NAMES = {
    '教育部', '交通运输部', '工业和信息化部', '国家民委',
    '国家卫生健康委', '农业农村部', '生态环境部', '应急管理部',
    '公安部', '司法部', '外交部', '国防部', '财政部',
    '水利部', '住房和城乡建设部', '自然资源部', '科学技术部',
    '文化和旅游部', '退役军人事务部', '国家中医药管理局',
    '中国科学院', '中国社会科学院', '中国工程院',
    '国家国防科工局', '国家体育总局', '海关总署',
    '中央统战部', '中央办公厅', '国务院侨办',
    '民用航空局', '国家铁路局', '国家邮政局',
    '中国地震局', '中国气象局', '国家海洋局',
    '中华全国总工会', '共青团中央', '全国妇联',
    '北京市', '天津市', '上海市', '重庆市',
}

# Degree/level markers (appear after province+city)
DEGREE_MARKERS = {
    '博士', '硕士', '学士', '学术', '专业', '学位',
    '博士学位', '硕士学位', '博士专业', '硕士专业',
    '学术学位', '专业学位', '特殊需求',
}

# Province/city suffixes
LOCATION_SUFFIXES = {'省', '市', '区', '县', '自治区', '自治州', '地区', '盟'}


def preprocess_image(img):
    """Preprocess image for better OCR with Chinese text."""
    gray = img.convert('L')
    arr = np.array(gray)
    threshold = np.median(arr) * 0.85
    binary = ((arr < threshold) * 255).astype(np.uint8)
    binary_img = Image.fromarray(binary, mode='L')
    w, h = binary_img.size
    return binary_img.resize((w * 2, h * 2), Image.LANCZOS)


def ocr_image(img_path):
    """OCR an image and return text."""
    img = Image.open(img_path)
    processed = preprocess_image(img)
    return pytesseract.image_to_string(processed, lang='chi_sim', config='--psm 4')


def extract_school_name(tokens):
    """
    Extract school name from OCR token list.

    OCR outputs space-separated tokens. Each line in the image is a table row:
    [序号] [学校名...] [主管部门] [省份] [城市] [学位类型] [985/211标记]

    Strategy: find the degree marker (博士/硕士), then work backwards through
    province/city/department markers to find where the school name ends.
    """
    if not tokens:
        return ""

    # First, find the degree section (博士 or 硕士)
    degree_idx = len(tokens)
    for i, token in enumerate(tokens):
        if token in ('博士', '硕士'):
            degree_idx = i
            break

    # Now work backwards from degree marker to find school name boundary
    # The tokens just before the degree marker are: [...city, province_suffix, province, dept, school_name]
    end_idx = degree_idx

    # Step backwards past: 学位, 学术/专业 (degree qualifiers)
    # e.g., "博士 学位" or "博士 学术 学位"
    while end_idx > 0 and tokens[end_idx - 1] in ('学位', '学术', '专业', '博士', '硕士', '特殊', '需求'):
        end_idx -= 1

    # Step backwards past province/city info
    # Pattern: [city_name] [市/州/地区] [province_name] [省/自治区]
    # e.g., "大连 市 辽宁 省" or "北京 市"
    # Look for known province names or location suffixes
    found_location = False
    while end_idx > 0:
        prev = tokens[end_idx - 1]
        if prev in LOCATION_SUFFIXES:
            # Skip the city/province suffix and the name before it
            end_idx -= 1  # skip 省/市/区
            found_location = True
            # Skip the city/province name
            if end_idx > 0:
                end_idx -= 1
            # Check if there's another level (province after city)
            # e.g., "大连 市 辽宁 省" -> skip "辽宁" and "省"
            if end_idx > 0 and tokens[end_idx - 1] in LOCATION_SUFFIXES:
                end_idx -= 1  # skip second suffix
                if end_idx > 0:
                    end_idx -= 1  # skip second location name
            continue
        elif prev in PROVINCE_NAMES or prev in DEPARTMENT_NAMES:
            end_idx -= 1
            found_location = True
            continue
        else:
            break

    # Now tokens[0:end_idx] should be the school name
    if end_idx == 0:
        # Fallback: take everything up to first province/dept marker
        for i, token in enumerate(tokens):
            if token in PROVINCE_NAMES or token in DEPARTMENT_NAMES:
                end_idx = i
                break
        else:
            end_idx = len(tokens)

    name = ''.join(tokens[:end_idx])

    # Clean: remove leading numbers and punctuation
    name = re.sub(r'^[\d\s.、)）\-—|｜·]+', '', name)
    # Remove artifacts from OCR
    name = name.strip('0123456789.、)） ()，,。|｜-— ')
    # Remove single-char noise at end
    name = re.sub(r'[^一-鿿a-zA-Z0-9（）()]{1,2}$', '', name)

    return name


def parse_schools(text):
    """Parse OCR output to extract school names."""
    schools = []
    seen = set()

    for line in text.split('\n'):
        line = line.strip()
        if not line:
            continue

        # Split into tokens (OCR adds spaces between Chinese chars)
        tokens = line.split()

        # Find first number token - this is the sequence number
        seq_idx = -1
        for i, t in enumerate(tokens):
            try:
                int(t)
                if 1 <= int(t) <= 500:
                    seq_idx = i
                    break
            except ValueError:
                continue

        if seq_idx == -1 or seq_idx >= len(tokens) - 2:
            continue

        # Extract school name from tokens after sequence number
        name = extract_school_name(tokens[seq_idx + 1:])

        # Validate
        valid_endings = ('大学', '学院', '学校', '研究院', '研究所')
        has_ending = any(name.endswith(e) for e in valid_endings)
        has_keyword = any(kw in name for kw in ('大学', '学院'))

        if has_keyword and len(name) >= 4 and len(name) <= 30:
            if name not in seen:
                seen.add(name)
                schools.append(name)

    return schools


def main():
    base_dir = Path('e:/try-agent/crawler_data')

    image_files = [
        ('doctoral', base_dir / 'doctoral-1-huabei.jpg', '华北'),
        ('doctoral', base_dir / 'doctoral-2-dongbei.jpg', '东北'),
        ('doctoral', base_dir / 'doctoral-3-huadong.jpg', '华东'),
        ('doctoral', base_dir / 'doctoral-4-huazhong.jpg', '华中/华南'),
        ('doctoral', base_dir / 'doctoral-5-xinan.jpg', '西南/西北'),
        ('masters', base_dir / 'masters-1.jpg', '硕士1'),
        ('masters', base_dir / 'masters-2.jpg', '硕士2'),
    ]

    all_doctoral = []
    all_masters = []

    for category, img_path, region in image_files:
        print(f"\n{'=' * 60}")
        print(f"OCR: {region} ({category})")
        print(f"{'=' * 60}")

        text = ocr_image(str(img_path))
        schools = parse_schools(text)

        if category == 'doctoral':
            all_doctoral.extend(schools)
        else:
            all_masters.extend(schools)

        print(f"Found {len(schools)} schools")
        for s in schools[:3]:
            print(f"  - {s}")

    # De-duplicate while preserving order
    all_doctoral = list(dict.fromkeys(all_doctoral))
    all_masters = list(dict.fromkeys(all_masters))

    print(f"\n{'=' * 60}")
    print(f"RESULTS")
    print(f"{'=' * 60}")
    print(f"Doctoral: {len(all_doctoral)} (expected ~400)")
    print(f"Masters: {len(all_masters)} (expected ~221)")
    print(f"Total: {len(all_doctoral) + len(all_masters)} (expected ~621)")

    output = {
        'schools': all_doctoral + all_masters,
        'count': len(all_doctoral) + len(all_masters),
        'doctoral': all_doctoral,
        'masters': all_masters,
        'doctoral_count': len(all_doctoral),
        'masters_count': len(all_masters),
        'source': 'OCR from gxzsxx.net images via tesseract'
    }

    outpath = base_dir / 'official_869_schools.json'
    with open(outpath, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\nSaved to {outpath}")


if __name__ == '__main__':
    main()
