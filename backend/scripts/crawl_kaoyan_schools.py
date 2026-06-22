"""
Crawl school list with 985/211/双一流/自划线 flags from kaoyan.cn API.

API: POST https://api.kaoyan.cn/pc/school/schoolList
Returns 1,117 schools with classification flags.

Usage: cd backend && PYTHONPATH=. python scripts/crawl_kaoyan_schools.py
"""
import json
import time
import sys
from pathlib import Path

import requests

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

API_URL = "https://api.kaoyan.cn/pc/school/schoolList"


def fetch_all_schools(page_size: int = 50, delay: float = 0.5) -> list[dict]:
    """Fetch all schools with pagination."""
    all_schools = []
    page = 1

    while True:
        payload = {
            "page": page,
            "limit": page_size,
            "province_id": "",
            "type": "",
            "feature": "",
            "school_name": "",
        }
        resp = requests.post(API_URL, json=payload, headers=HEADERS, timeout=30)
        data = resp.json()

        if data.get("code") != "0000":
            print(f"API error: {data.get('message')}")
            break

        result = data["data"]
        schools = result.get("data", result.get("list", []))
        if not schools:
            break

        all_schools.extend(schools)
        total = result.get("total", len(schools))
        print(f"  Page {page}: {len(schools)} schools (total: {len(all_schools)}/{total})")

        if len(all_schools) >= total:
            break

        page += 1
        time.sleep(delay)

    return all_schools


def classify_schools(schools: list[dict]) -> dict:
    """Summarize school classifications."""
    stats = {
        "total": len(schools),
        "is_985": sum(1 for s in schools if s.get("is_985") == 1),
        "is_211": sum(1 for s in schools if s.get("is_211") == 1),
        "syl": sum(1 for s in schools if s.get("syl") == 1),  # 双一流
        "is_zihuaxian": sum(1 for s in schools if s.get("is_zihuaxian") == 1),  # 自划线
        "is_ordinary": sum(1 for s in schools if s.get("is_ordinary") == 1),
    }
    return stats


def main():
    print("Fetching school list from kaoyan.cn...")
    schools = fetch_all_schools()
    print(f"Fetched {len(schools)} schools total")

    stats = classify_schools(schools)
    print("\nClassification stats:")
    for k, v in stats.items():
        print(f"  {k}: {v}")

    # Save raw data
    output_path = OUTPUT_DIR / "schools_raw.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({"schools": schools, "stats": stats}, f, ensure_ascii=False, indent=2)
    print(f"\nSaved to {output_path}")

    # Print sample
    print("\nSample Top 10 by ranking:")
    ranked = sorted(schools, key=lambda s: s.get("rk_rank", 99999))
    for s in ranked[:10]:
        tags = []
        if s.get("is_985") == 1: tags.append("985")
        if s.get("is_211") == 1: tags.append("211")
        if s.get("syl") == 1: tags.append("双一流")
        if s.get("is_zihuaxian") == 1: tags.append("自划线")
        print(f"  {s['school_name']} (id={s['school_id']}) "
              f"rank={s.get('rk_rank','?')} tags={tags} "
              f"province={s.get('province_name','?')}")


if __name__ == "__main__":
    main()
