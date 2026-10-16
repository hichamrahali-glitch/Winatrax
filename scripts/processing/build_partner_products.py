"""Main HS2 chapters traded with each partner, per year, for the country view of the world map.

Input : data/processed/lu_trade_hs2_annual.csv.gz (written by the ingestion command),
        or another copy of that file passed as the first argument.
Output: data/derived/partner_products.json
        {"years": [1999, ...],
         "partners": {code: {"Exports"|"Imports": {year: [[total_value, total_qty], [[hs2, value, qty], ...]]}}}}
        Chapters kept per partner/flow/year: the 20 largest by value plus the 20 largest by
        weight (the page re-ranks by the chosen measure); totals cover every chapter, so the
        page can show what share the listed chapters leave as "other".
        Value in million EUR, quantity in thousand tonnes (same units as app_data.json).
        Partner codes are 2 letters (aggregates such as WORLD or EXT_EU are left out).

Run from the project root:  python -m scripts.processing.build_partner_products [annual.csv(.gz)]
"""
import json
import sys
from pathlib import Path

import pandas as pd

from scripts._bootstrap import PROJECT_ROOT
from project_paths import DERIVED_DATA_DIR, PROCESSED_DATA_DIR

SRC = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else PROCESSED_DATA_DIR / "lu_trade_hs2_annual.csv.gz"
OUT = DERIVED_DATA_DIR / "partner_products.json"
FLOWS = {"Import": "Imports", "Export": "Exports"}
KEEP = 20


def dumps(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def sig(x, digits=3):
    """Round to 3 significant figures and drop '.0' to keep the JSON small."""
    if not x:
        return 0
    v = float(f"{x:.{digits}g}")
    return int(v) if v == int(v) else v


# keep_default_na=False: partner code "NA" is Namibia, not a missing value
df = pd.read_csv(SRC, dtype={"product": str}, keep_default_na=False,
                 usecols=["time", "partner", "product", "flow", "VALUE_IN_EUROS", "QUANTITY_IN_100KG"])
df = df[(df["product"] != "TOTAL") & (df["partner"].str.len() == 2)]
df["v"] = pd.to_numeric(df["VALUE_IN_EUROS"], errors="coerce").fillna(0) / 1e6      # million EUR
df["q"] = pd.to_numeric(df["QUANTITY_IN_100KG"], errors="coerce").fillna(0) / 1e4   # thousand tonnes
df = df[(df["v"] > 0) | (df["q"] > 0)]

out = {"years": sorted(int(y) for y in df["time"].unique()), "partners": {}}
for (partner, flow, year), g in df.groupby(["partner", "flow", "time"], sort=True):
    keep = set(g.nlargest(KEEP, "v")["product"]) | set(g.nlargest(KEEP, "q")["product"])
    rows = g[g["product"].isin(keep)].sort_values("v", ascending=False)
    out["partners"].setdefault(partner, {}).setdefault(FLOWS[flow], {})[str(year)] = [
        [sig(g["v"].sum()), sig(g["q"].sum())],
        [[p, sig(v), sig(q)] for p, v, q in zip(rows["product"], rows["v"], rows["q"])],
    ]

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(dumps(out), encoding="utf-8")
print(f"{OUT}: {len(out['partners'])} partners, {out['years'][0]}-{out['years'][-1]}, {OUT.stat().st_size / 1e6:.1f} MB")
