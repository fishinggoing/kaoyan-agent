"""Fix school levels on server using yantu source data — one-shot script."""
import json, sqlite3, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.data.school_levels import classify_level, classify_category

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

with open(os.path.join(BASE_DIR, "data", "yantu_schools.json"), "r", encoding="utf-8") as f:
    raw = json.load(f)
schools_data = raw.get("data", raw if isinstance(raw, list) else [])

name_map = {}
for item in schools_data:
    name = item.get("name", "").strip()
    code = item.get("code", "").strip()
    if not name or not code:
        continue
    uc = code[5:10] if len(code) >= 10 else code
    if name not in name_map:
        cat = classify_category(name)
        level = classify_level(uc, name) if cat == "GRAD_EXAM" else "REGULAR"
        name_map[name] = (level, cat)

db = sqlite3.connect(os.path.join(BASE_DIR, "gradschool.db"))
db.text_factory = str

col = db.execute("SELECT COUNT(*) FROM pragma_table_info('schools') WHERE name='category'").fetchone()[0]
if not col:
    db.execute("ALTER TABLE schools ADD COLUMN category VARCHAR(20)")
    db.commit()
    print("Added category column")

updated = 0
for sid, name in db.execute("SELECT id, name FROM schools"):
    info = name_map.get(name)
    if info:
        level, cat = info
        db.execute("UPDATE schools SET level=?, category=? WHERE id=?", [level, cat, sid])
        updated += 1
    else:
        db.execute("UPDATE schools SET category=? WHERE id=?", ["GRAD_EXAM", sid])

db.commit()

print(f"\nUpdated {updated} schools")
print("\nLevels:")
for row in db.execute("SELECT level, COUNT(*) FROM schools GROUP BY level ORDER BY COUNT(*) DESC"):
    print(f"  {row[0]:12s} {row[1]:5d}")
print("\nCategories:")
for row in db.execute("SELECT category, COUNT(*) FROM schools GROUP BY category ORDER BY COUNT(*) DESC"):
    print(f"  {row[0] or 'NULL':12s} {row[1]:5d}")
print("\nVerify:")
for name in ["武汉大学", "北京邮电大学", "华中科技大学", "北京航空航天大学"]:
    r = db.execute("SELECT name, level, category FROM schools WHERE name=?", [name]).fetchone()
    if r:
        print(f"  {r[0]:20s} level={r[1]:6s} cat={r[2]}")

db.close()
print("\nDone.")
