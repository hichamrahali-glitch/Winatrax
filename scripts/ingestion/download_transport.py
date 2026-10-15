"""Download the data for the transport mode & CO2 page.

- DS-059334  EU trade by mode of transport (customs data: extra-EU trade only)
             reporter LU, all partners, all modes, quantity (kg) and value (EUR):
               * product TOTAL, annual from 2015          -> lu_modes_total.json
               * HS2 chapters, latest full year           -> lu_modes_hs2_<year>.json
- tran_hv_frmod  Modal split of inland freight transport (% of tonne-km), LU
- avia_gooc      Freight and mail through Luxembourg airport (tonnes)
- env_ac_ainah_r2  Air emissions accounts: CO2 by economic activity (NACE), LU

Output: data/raw/api_transport/*.json

Run from the project root:  python -m scripts.ingestion.download_transport
"""
import json
from pathlib import Path

from scripts._bootstrap import PROJECT_ROOT
from ingestion.eurostat_api import comext_fetch, dissemination_fetch
from project_paths import RAW_DATA_DIR

CACHE = RAW_DATA_DIR / "api_transport"

total = comext_fetch("DS-059334",
                     [("reporter", "LU"), ("product", "TOTAL"), ("freq", "A"), ("sinceTimePeriod", "2015"),
                      ("indicators", "QUANTITY_KG"), ("indicators", "VALUE_EUR")],
                     CACHE / "lu_modes_total.json")
print("modes, total:", "ok" if total else "failed")

# latest year with data for both flows
d = json.loads(Path(total).read_text())
years = sorted(d["dimension"]["time"]["category"]["index"])
year = years[-2] if len(years) > 1 else years[-1]          # last entry is the running (partial) year
chapters = [f"{i:02d}" for i in range(1, 100) if i not in (77, 98)]
for k in range(0, len(chapters), 10):                       # batches of 10 chapters (size limit)
    batch = chapters[k:k + 10]
    params = [("reporter", "LU"), ("freq", "A"), ("time", year),
              ("indicators", "QUANTITY_KG"), ("indicators", "VALUE_EUR")] + [("product", c) for c in batch]
    f = comext_fetch("DS-059334", params, CACHE / f"lu_modes_hs2_{year}_{batch[0]}-{batch[-1]}.json")
    print(f"modes by HS2 {batch[0]}-{batch[-1]}, {year}:", "ok" if f else "failed")

dissemination_fetch("tran_hv_frmod", [("geo", "LU"), ("sinceTimePeriod", "2015")], CACHE / "modal_split.json")
dissemination_fetch("avia_gooc", [("geo", "LU"), ("freq", "A"), ("unit", "T"), ("tra_meas", "FRM_LD_NLD"),
                                  ("schedule", "TOTAL"), ("tra_cov", "TOTAL"), ("sinceTimePeriod", "2015")],
                    CACHE / "airport_freight.json")
dissemination_fetch("env_ac_ainah_r2", [("geo", "LU"), ("airpol", "CO2"), ("unit", "T"),
                                        ("sinceTimePeriod", "2015")], CACHE / "co2_by_activity.json")
print("modal split, airport freight, CO2 accounts: ok")
