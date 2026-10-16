"""Download Luxembourg's trade from Eurostat Comext (DS-045409) via the API.

Scope : reporter = Luxembourg, all partners, products = HS2 chapters (01-99)
        + TOTAL, imports and exports, value (EUR) and quantity (100 kg),
        monthly and annual from 1999.
Output: data/raw/api/<freq>_<product>.json   (cache, one file per request)
        data/processed/lu_trade_hs2_monthly.csv.gz
        data/processed/lu_trade_hs2_annual.csv.gz

Requests that are too large are queued asynchronously by Eurostat, so we fetch
one product at a time. Re-running only downloads products whose cache file is
missing; delete data/raw/api/ to force a full refresh (new months).

Run from the project root:  python -m scripts.ingestion.download_eurostat
"""
import pandas as pd

from scripts._bootstrap import PROJECT_ROOT
from ingestion.eurostat_api import QueryTooLarge, comext_fetch, comext_parse
from project_paths import PROCESSED_DATA_DIR, RAW_DATA_DIR

REPORTER = "LU"
FIRST_YEAR = 1999
PRODUCTS = ["TOTAL"] + [f"{i:02d}" for i in range(1, 100)]
CACHE_DIR = RAW_DATA_DIR / "api"
OUT_DIR = PROCESSED_DATA_DIR
OUT_DIR.mkdir(parents=True, exist_ok=True)

COLUMNS = ["freq", "time", "reporter", "partner", "partner_label", "product",
           "product_label", "flow", "VALUE_IN_EUROS", "QUANTITY_IN_100KG"]

for freq in ("A", "M"):
    print(f"== Frequency {freq}")
    since = f"{FIRST_YEAR}-01" if freq == "M" else str(FIRST_YEAR)
    parts = []
    for p in PRODUCTS:
        params = [("reporter", REPORTER), ("product", p), ("freq", freq),
                  ("sinceTimePeriod", since), ("flow", 1), ("flow", 2),
                  ("indicators", "VALUE_IN_EUROS"), ("indicators", "QUANTITY_IN_100KG")]
        try:
            f = comext_fetch("DS-045409", params, CACHE_DIR / f"{freq}_{p}.json")
        except QueryTooLarge:
            # Eurostat answers 413 for codes with no data too (chapters 77 and 98)
            f = None
        print(f"  {p:<5} {'skipped' if f is None else 'ok'}")
        if f is not None:
            df = comext_parse(f)
            if df is not None:
                parts.append(df)

    long = pd.concat(parts, ignore_index=True)
    wide = (long.pivot_table(index=["freq", "reporter", "partner", "partner_label", "product",
                                    "product_label", "flow", "time"],
                             columns="indicators", values="value", aggfunc="first")
                .reset_index())
    wide.columns.name = None
    wide["flow"] = wide["flow"].map({"1": "Import", "2": "Export"})
    wide = wide[COLUMNS].sort_values(["product", "partner", "flow", "time"], kind="stable")

    out = OUT_DIR / f"lu_trade_hs2_{'monthly' if freq == 'M' else 'annual'}.csv.gz"
    wide.to_csv(out, index=False, float_format="%.15g")
    print(f"Wrote {out} ({len(wide):,} rows)")
