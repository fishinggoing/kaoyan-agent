"""
Crawl school-specific score lines from kaoyan.cn API.

API: POST https://api.kaoyan.cn/pc/school/schoolScore
Params: {"school_id": int, "year": "2025"}
Returns score lines with department-level detail, single-subject scores,
and difference from national line (diff_*).

Usage: cd backend && PYTHONPATH=. python scripts/crawl_kaoyan_school_scores.py
"""
import json
import sys
import time
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

API_URL = "https://api.kaoyan.cn/pc/school/schoolScore"
YEARS = ["2022", "2023", "2024", "2025", "2026"]
CHECKPOINT_PATH = OUTPUT_DIR / "school_scores_checkpoint.json"


def log(msg: str):
    print(msg, flush=True)


def load_schools() -> list[dict]:
    path = OUTPUT_DIR / "schools_raw.json"
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data["schools"]


def load_checkpoint() -> tuple[list[dict], dict, list[dict], int]:
    if CHECKPOINT_PATH.exists():
        with open(CHECKPOINT_PATH, encoding="utf-8") as f:
            cp = json.load(f)
        return cp["records"], cp["stats"], cp.get("errors", []), cp.get("last_index", -1)
    return [], {"total_schools": 0, "with_data": 0, "without_data": 0, "errors": 0}, [], -1


def save_checkpoint(records: list[dict], stats: dict, errors: list[dict], last_index: int):
    with open(CHECKPOINT_PATH, "w", encoding="utf-8") as f:
        json.dump({"records": records, "stats": stats, "errors": errors, "last_index": last_index},
                  f, ensure_ascii=False)


def fetch_school_scores(school_id: int, year: str, timeout: int = 30) -> list[dict]:
    payload = {"school_id": school_id, "year": year}
    resp = requests.post(API_URL, json=payload, headers=HEADERS, timeout=timeout)
    data = resp.json()
    if data.get("code") != "0000":
        return []
    return data.get("data", [])


def main():
    schools = load_schools()
    all_records, stats, errors, start_index = load_checkpoint()

    if start_index >= 0:
        log(f"Resuming from checkpoint: {len(all_records)} records, index={start_index}")
        stats["total_schools"] = len(schools)
    else:
        stats["total_schools"] = len(schools)
        log(f"Loaded {len(schools)} schools from schools_raw.json")

    start_index = max(start_index, -1)

    for i in range(start_index + 1, len(schools)):
        school = schools[i]
        sid = school["school_id"]
        sname = school["school_name"]
        school_records = 0

        for year in YEARS:
            try:
                records = fetch_school_scores(sid, year)
                if records:
                    all_records.extend(records)
                    school_records += len(records)
            except Exception as e:
                errors.append({"school_id": sid, "school_name": sname, "year": year, "error": str(e)})
                stats["errors"] += 1
            time.sleep(0.3)

        if school_records > 0:
            stats["with_data"] += 1
            if stats["with_data"] <= 10 or stats["with_data"] % 50 == 0:
                log(f"  [{stats['with_data']}/{i+1}] {sname} (id={sid}): {school_records} records")
        else:
            stats["without_data"] += 1

        # Checkpoint every 100 schools
        if (i + 1) % 100 == 0:
            stats["total_records"] = len(all_records)
            save_checkpoint(all_records, stats, errors, i)
            log(f"  [checkpoint] {i+1}/{len(schools)} | with_data={stats['with_data']} "
                f"without_data={stats['without_data']} errors={stats['errors']} "
                f"records={len(all_records)}")

    stats["total_records"] = len(all_records)

    # Save final
    output_path = OUTPUT_DIR / "school_scores_raw.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({"records": all_records, "stats": stats, "errors": errors},
                  f, ensure_ascii=False, indent=2)
    log(f"\nSaved {len(all_records)} records to {output_path}")
    log(f"Stats: with_data={stats['with_data']} without_data={stats['without_data']} errors={stats['errors']}")

    # Clean checkpoint
    if CHECKPOINT_PATH.exists():
        CHECKPOINT_PATH.unlink()


if __name__ == "__main__":
    main()
