"""Download full product detail (HS2 -> HS4 -> HS6 -> CN8) for Luxembourg's
main partner countries, for the latest full year.

Scope : reporter = Luxembourg, one request per partner: all product codes,
        imports and exports, value (EUR) and quantity (100 kg), annual.
        Partners = the N_PARTNERS biggest by total trade value (exports +
        imports) in that year, from the HS2 download.
Output: data/raw/api_cn8/<year>_<partner>.json   (cache, one file per partner)

Run from the project root, after 00_:  python python/05_download_partner_detail.py
"""
from pathlib import Path

import pandas as pd

from eurostat_api import AGGREGATES, comext_fetch

N_PARTNERS = 40
CACHE_DIR = Path("data/raw/api_cn8")
NOT_COUNTRIES = set(AGGREGATES) | {"QQ", "QR", "QS", "QU", "QV", "QW", "QX", "QY", "QZ", "XC", "XL"}

annual = pd.read_csv("data/processed/lu_trade_hs2_annual.csv.gz", dtype=str, keep_default_na=False)
annual["VALUE_IN_EUROS"] = pd.to_numeric(annual["VALUE_IN_EUROS"].replace("", None))
tot = annual[annual["product"] == "TOTAL"]
year = tot.loc[tot["partner"] == "WORLD", "time"].max()   # latest full year
partners = (tot[(tot["time"] == year) & ~tot["partner"].isin(NOT_COUNTRIES)]
            .groupby("partner")["VALUE_IN_EUROS"].sum().sort_values(ascending=False)
            .head(N_PARTNERS).index.tolist())

print(f"Year {year}: {len(partners)} partners")
for p in partners:
    params = [("reporter", "LU"), ("partner", p), ("freq", "A"), ("time", year),
              ("flow", 1), ("flow", 2),
              ("indicators", "VALUE_IN_EUROS"), ("indicators", "QUANTITY_IN_100KG")]
    f = comext_fetch("DS-045409", params, CACHE_DIR / f"{year}_{p}.json")
    print(f"  {p}  {'ok' if f else 'failed'}")
