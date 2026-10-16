"""Product tree per partner country (HS2 > HS4 > HS6 > CN8) for the latest full
year: data/derived/partners/<code>.json.

Input : data/raw/api_cn8/<year>_<partner>.json (written by
        python -m scripts.ingestion.download_partner_detail)
Output: data/derived/partners/<partner>.json
        {"year": "2025",
         "value"|"quantity": {"Exports"|"Imports": tree}, "labels": {code: product name}}
        Tree node: {"c": code, "v": value, "k": [children], "o": other, "n": items grouped}

At every level the children that make up 95% of their parent are kept (at least
3, at most 20); the rest is summed into "other", shown as "not itemised" on the
page. Deeper or older figures are fetched from the Eurostat API by the page.
Value in million EUR, quantity in thousand tonnes (same units as app_data.json).

Run from the project root:  python -m scripts.processing.build_partner_trees
"""
import json

from scripts._bootstrap import PROJECT_ROOT
from ingestion.eurostat_api import comext_parse
from processing.trade_tree import partner_detail
from project_paths import DERIVED_DATA_DIR, RAW_DATA_DIR

CN8_DIR = RAW_DATA_DIR / "api_cn8"
OUT_DIR = DERIVED_DATA_DIR / "partners"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def dumps(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


files = sorted(CN8_DIR.glob("*.json"))
if not files:
    raise SystemExit(f"No downloads in {CN8_DIR} - run scripts.ingestion.download_partner_detail first.")

for p in OUT_DIR.glob("*.json"):
    p.unlink()

written, year = [], None
for f in files:
    year, partner = f.stem.split("_", 1)
    df = comext_parse(f)
    if df is None:
        print(f"  {partner}: no data")
        continue
    out = partner_detail(df, year)
    (OUT_DIR / f"{partner}.json").write_text(dumps(out), encoding="utf-8")
    written.append(partner)

size_mb = sum(p.stat().st_size for p in OUT_DIR.glob("*.json")) / 1e6
print(f"{OUT_DIR}: {len(written)} partners for {year} ({size_mb:.1f} MB)")
