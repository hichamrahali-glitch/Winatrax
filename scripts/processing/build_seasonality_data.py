"""Monthly series for the seasonality section of app.py.

Input : data/processed/lu_trade_hs2_monthly.csv.gz (written by 00_download_eurostat.py),
        or another copy of that file passed as the first argument.
Output: data/derived/seasonality.json
        {"months": ["1999-01", ...],
         "series": {product: {"Imports"|"Exports": {"value": [...], "quantity": [...]}}}}
        partner = all countries of the world, product = TOTAL + HS2 chapters (99 left out:
        confidential trade has no meaningful season). Value in million EUR, quantity in
        thousand tonnes (same units as app_data.json); null where Eurostat has no figure.

Run from the project root:  python -m scripts.processing.build_seasonality_data [monthly.csv(.gz)]
"""
import json
import sys
from pathlib import Path

import pandas as pd

from scripts._bootstrap import PROJECT_ROOT
from project_paths import DERIVED_DATA_DIR, PROCESSED_DATA_DIR

SRC = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else PROCESSED_DATA_DIR / "lu_trade_hs2_monthly.csv.gz"
OUT = DERIVED_DATA_DIR / "seasonality.json"
FLOWS = {"Import": "Imports", "Export": "Exports"}


def dumps(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


# ---- 1. Load: world totals only (the file holds every partner, ~270 MB) ------
parts = []
for chunk in pd.read_csv(SRC, dtype={"product": str}, keep_default_na=False, chunksize=2_000_000,
                         usecols=["time", "partner", "product", "flow", "VALUE_IN_EUROS", "QUANTITY_IN_100KG"]):
    parts.append(chunk[chunk["partner"] == "WORLD"])
df = pd.concat(parts, ignore_index=True)
df = df[df["product"] != "99"]
for col in ("VALUE_IN_EUROS", "QUANTITY_IN_100KG"):
    df[col] = pd.to_numeric(df[col], errors="coerce")

months = pd.period_range(df["time"].min(), df["time"].max(), freq="M").strftime("%Y-%m").tolist()


# ---- 2. One aligned monthly array per product / flow / measure --------------
def series(s, divisor, digits):
    s = s.reindex(months)
    return [None if pd.isna(v) or v <= 0 else round(v / divisor, digits) for v in s]


out = {"months": months, "series": {}}
for (product, flow), g in df.groupby(["product", "flow"]):
    g = g.set_index("time")
    out["series"].setdefault(product, {})[FLOWS[flow]] = {
        "value": series(g["VALUE_IN_EUROS"], 1e6, 3),         # EUR -> million EUR
        "quantity": series(g["QUANTITY_IN_100KG"], 1e4, 3),  # 100 kg -> thousand tonnes
    }

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(dumps(out), encoding="utf-8")
print(f"{OUT}: {len(out['series'])} products, {months[0]} to {months[-1]}, {OUT.stat().st_size / 1e6:.1f} MB")
