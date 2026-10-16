"""Download the total trade of every Comext reporter, for the country comparison
(imports and exports per inhabitant).

Trade : DS-045409, all reporters, partner = WORLD, product = TOTAL, imports and
        exports, value (EUR) and quantity (100 kg), annual from 1999. The
        reporters are the 27 EU member states, the United Kingdom (until 2019)
        and 4 country groups (EU, EU27_2020, euro area, euro area 21); the
        groups have no trade with WORLD, so scripts/build-data.mjs sums their
        members instead.
Output: data/raw/eu_trade_totals.json   (read by scripts/build-data.mjs)

Population is not downloaded here: it comes from the World Bank's World
Development Indicators (series SP.POP.TOTL), exported from
https://databank.worldbank.org/source/world-development-indicators as
data/raw/wdi_population.csv (one row per country, one column per year).

Run from the project root:  python -m scripts.ingestion.download_country_totals
"""
from scripts._bootstrap import PROJECT_ROOT
from ingestion.eurostat_api import comext_fetch
from project_paths import RAW_DATA_DIR

OUT = RAW_DATA_DIR / "eu_trade_totals.json"

trade = comext_fetch(
    "DS-045409",
    [("partner", "WORLD"), ("product", "TOTAL"), ("freq", "A"), ("sinceTimePeriod", "1999"),
     ("flow", 1), ("flow", 2), ("indicators", "VALUE_IN_EUROS"), ("indicators", "QUANTITY_IN_100KG")],
    OUT)
print(f"{OUT}:", "ok" if trade else "failed")
