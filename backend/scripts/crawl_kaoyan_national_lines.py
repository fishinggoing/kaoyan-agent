"""
Crawl REAL national line data from kaoyan.cn (掌上考研) API.

This replaces the synthetic national lines currently hard-coded in
seed_majors_and_scores.py with ACTUAL data from 2022-2026.

API: POST https://api.kaoyan.cn/pc/school/specialScoreGj
Input: {"special_code": "XXXX"} (4-digit discipline code)
Output: [{total, single_100, single_150, year, name, area_type, degree_type, code}]

Usage: cd backend && PYTHONPATH=. python scripts/crawl_kaoyan_national_lines.py
"""
import json
import time
import sys
from pathlib import Path

import requests

# Paths
OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent / "crawler_data" / "kaoyan_cn"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.kaoyan.cn/",
    "Content-Type": "application/json",
    "Origin": "https://www.kaoyan.cn",
}


def fetch_all_discipline_codes() -> list[str]:
    """Get all 4-digit discipline codes from the filter JSON."""
    url = "https://static.kaoyan.cn/json/special/special_score_gj_filter.json"
    resp = requests.get(url, headers=HEADERS, timeout=30)
    data = resp.json()["data"]

    codes = set()
    for item in data.get("second_class", []):
        code = item.get("code", "")
        if len(code) == 4 and code.isdigit():
            codes.add(code)

    # Also add from the speciality catalog
    catalog_url = "https://static.kaoyan.cn/json/special/special_score_gj.json"
    resp2 = requests.get(catalog_url, headers=HEADERS, timeout=30)
    cat_data = resp2.json()["data"]
    for spe_id, entry in cat_data.items():
        code = entry.get("special_code", "")
        if len(code) >= 4:
            codes.add(code[:4])

    return sorted(codes)


def crawl_national_lines(codes: list[str], delay: float = 0.5):
    """Fetch national line data for all discipline codes."""
    all_records: list[dict] = []
    errors: list[str] = []
    api_url = "https://api.kaoyan.cn/pc/school/specialScoreGj"

    for i, code in enumerate(codes):
        try:
            resp = requests.post(
                api_url,
                json={"special_code": code},
                headers=HEADERS,
                timeout=15,
            )
            if resp.status_code == 200:
                result = resp.json()
                if result.get("code") == "0000" and result.get("data"):
                    for record in result["data"]:
                        record["query_code"] = code  # preserve query context
                    all_records.extend(result["data"])
                else:
                    errors.append(f"{code}: {result.get('message', 'unknown')}")
            else:
                errors.append(f"{code}: HTTP {resp.status_code}")

            if i % 20 == 19:
                print(f"  ... {i + 1}/{len(codes)} codes done, {len(all_records)} records")

        except Exception as e:
            errors.append(f"{code}: {e}")

        time.sleep(delay)

    return all_records, errors


def summarize_data(records: list[dict]):
    """Print summary statistics."""
    years = sorted(set(r["year"] for r in records))
    codes = set(r["query_code"] for r in records)
    area_types = set(r.get("area_type", "?") for r in records)
    degree_types = set(r.get("degree_type", "?") for r in records)

    print(f"\nTotal records: {len(records)}")
    print(f"Years: {years}")
    print(f"Unique 4-digit codes: {len(codes)}")
    print(f"Area types: {area_types}")
    print(f"Degree types: {degree_types} (1=专硕, 2=学硕)")

    # Show a few sample records
    for r in records[:5]:
        print(f"  {r['year']} {r['name']} {r['area_type']}类 "
              f"total={r['total']} single100={r['single_100']} single150={r['single_150']}")


def main():
    print("=== Fetching discipline codes ===")
    codes = fetch_all_discipline_codes()
    print(f"Found {len(codes)} unique 4-digit codes")

    print("\n=== Crawling national lines ===")
    records, errors = crawl_national_lines(codes)
    print(f"\nDone: {len(records)} records, {len(errors)} errors")
    if errors:
        for e in errors[:10]:
            print(f"  ERROR: {e}")

    summarize_data(records)

    # Save raw data
    output_path = OUTPUT_DIR / "national_lines_all.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({"records": records, "errors": errors}, f, ensure_ascii=False, indent=2)
    print(f"\nSaved to {output_path}")

    # Build year→category→scores index for our DB schema
    # Group by (year, code, area_type, degree_type)
    indexed: dict[int, dict[str, list]] = {}
    for r in records:
        year = r["year"]
        if year not in indexed:
            indexed[year] = {}
        key = f"{r['code']}_{r['area_type']}_{r['degree_type']}"
        indexed[year][key] = [r["total"], r["single_100"], r["single_150"]]

    index_path = OUTPUT_DIR / "national_lines_indexed.json"
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(indexed, f, ensure_ascii=False, indent=2)
    print(f"Indexed version saved to {index_path}")


if __name__ == "__main__":
    main()
