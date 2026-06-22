"""
Enrich school levels using verified data from kaoyan.cn.

Maps kaoyan.cn school names to our DB schools via fuzzy matching,
then updates level fields (985/211/双一流/自划线) for unmatched or
incorrectly classified schools.

Usage: cd backend && PYTHONPATH=. python scripts/enrich_school_levels.py
"""
import json
import sys
from pathlib import Path
from difflib import SequenceMatcher

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.database import SessionLocal

KAOYAN_SCHOOLS = (
    Path(__file__).resolve().parent.parent.parent
    / "crawler_data" / "kaoyan_cn" / "schools_raw.json"
)


def load_kaoyan_schools() -> list[dict]:
    with open(KAOYAN_SCHOOLS, "r", encoding="utf-8") as f:
        return json.load(f)["schools"]


def fuzzy_match(name: str, candidates: dict[str, int], min_ratio: float = 0.8) -> int | None:
    """Find best fuzzy match from name to candidate (name→id) dict."""
    best_id, best_score = None, 0.0
    for cname, cid in candidates.items():
        ratio = SequenceMatcher(None, name, cname).ratio()
        if ratio > best_score:
            best_score = ratio
            best_id = cid
    return best_id if best_score >= min_ratio else None


def main():
    dry_run = "--dry-run" in sys.argv
    db = SessionLocal()
    kaoyan_schools = load_kaoyan_schools()
    print(f"Loaded {len(kaoyan_schools)} kaoyan.cn schools")

    # Build name→id mapping for our DB schools (考研高校 only)
    db_schools = db.execute(
        text("SELECT id, name FROM schools WHERE category = 'GRAD_EXAM'")
    ).fetchall()
    db_name_to_id: dict[str, int] = {r[1]: r[0] for r in db_schools}
    db_id_to_name: dict[int, str] = {r[0]: r[1] for r in db_schools}
    print(f"DB has {len(db_schools)} GRAD_EXAM schools")

    # Track levels from kaoyan.cn
    ky_levels: dict[str, str] = {}  # school_name → level string
    stats = {"985": 0, "211": 0, "双一流": 0, "普本": 0, "unmatched": 0}

    for ks in kaoyan_schools:
        name = ks["school_name"]
        if ks.get("is_985") == 1:
            ky_levels[name] = "985"
        elif ks.get("is_211") == 1:
            ky_levels[name] = "211"
        elif ks.get("syl") == 1:
            ky_levels[name] = "双一流"
        else:
            ky_levels[name] = "普本"

    # Match and report
    matched = 0
    mismatches: list[tuple[str, str, str, str]] = []  # name, db_level, ky_level, match_type

    for ky_name, ky_level in ky_levels.items():
        # Try exact match first
        if ky_name in db_name_to_id:
            db_id = db_name_to_id[ky_name]
            db_name = ky_name
            matched += 1
        else:
            # Fuzzy match
            db_id = fuzzy_match(ky_name, db_name_to_id)
            if db_id is None:
                stats["unmatched"] += 1
                continue
            db_name = db_id_to_name[db_id]
            matched += 1

        # Get current DB level
        current = db.execute(
            text("SELECT level FROM schools WHERE id = :id"),
            {"id": db_id},
        ).scalar()

        stats[ky_level] += 1

        # Check mismatch
        if current != ky_level:
            mismatches.append((db_name, current, ky_level, "exact" if ky_name == db_name else "fuzzy"))

    print(f"\nMatched: {matched}/{len(ky_levels)}, Unmatched: {stats['unmatched']}")
    print(f"Level distribution from kaoyan.cn: 985={stats['985']}, 211={stats['211']}, "
          f"双一流={stats['双一流']}, 普本={stats['普本']}")

    print(f"\nMismatched levels ({len(mismatches)}):")
    for name, db_lvl, ky_lvl, match_type in mismatches[:30]:
        print(f"  [{match_type}] {name}: DB={db_lvl} → kaoyan={ky_lvl}")

    if dry_run:
        print("\n--dry-run mode, no changes made")
    elif mismatches:
        print(f"\nUpdating {len(mismatches)} schools...")
        updated = 0
        for name, db_lvl, ky_lvl, match_type in mismatches:
            db.execute(
                text("UPDATE schools SET level = :lvl WHERE name = :name"),
                {"lvl": ky_lvl, "name": name},
            )
            updated += 1
        db.commit()
        print(f"Updated {updated} school levels")
    else:
        print("\nNo mismatches to fix")

    db.close()


if __name__ == "__main__":
    main()
