"""Download total trade of every EU reporter country, plus population, for the
country comparison (Luxembourg vs other countries).

Trade     : DS-045409, all reporters, partner = WORLD, product = TOTAL, imports
            and exports, value (EUR) and quantity (100 kg), annual from 1999.
            Reporters are the EU member states (and the UK until it left).
Population: demo_pjan (population on 1 January), total, all ages, from 1999.
Output    : data/raw/api_countries/trade_totals.json
            data/raw/api_countries/population.json

Run from the project root:  python python/06_download_country_totals.py
"""
from pathlib import Path

from eurostat_api import comext_fetch

CACHE = Path("data/raw/api_countries")

trade = comext_fetch(
    "DS-045409",
    [("partner", "WORLD"), ("product", "TOTAL"), ("freq", "A"), ("sinceTimePeriod", "1999"),
     ("flow", 1), ("flow", 2), ("indicators", "VALUE_IN_EUROS"), ("indicators", "QUANTITY_IN_100KG")],
    CACHE / "trade_totals.json")
print("trade totals:", "ok" if trade else "failed")

# Population comes from the general dissemination API (not Comext).
POP_URL = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/demo_pjan"
pop_file = CACHE / "population.json"
if not pop_file.exists():
    import requests
    res = requests.get(POP_URL, params={"format": "JSON", "age": "TOTAL", "sex": "T",
                                        "sinceTimePeriod": "1999"}, timeout=300)
    res.raise_for_status()
    pop_file.write_bytes(res.content)
print("population:", "ok" if pop_file.exists() else "failed")
