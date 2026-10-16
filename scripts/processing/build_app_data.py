"""Partner rankings over time for the world map: data/derived/app_data.json and
one file per HS2 chapter in data/derived/products/.

Input : data/processed/lu_trade_hs2_monthly.csv.gz (written by the ingestion
        command), or another copy of that file passed as the first argument,
        and assets/hs2_labels.json (short names and icons for the HS2 chapters).
Output: data/derived/app_data.json       frames, country names, HS2 chapters,
                                         product list and the all-goods rankings
        data/derived/products/<HS2>.json rankings for one chapter

Each frame is the total over the previous 12 months, so seasonal swings do not
move the ranking. Two measures are built:
  quantity: QUANTITY_IN_100KG, stored in thousand tonnes
  value   : VALUE_IN_EUROS,    stored in million EUR
Rankings are computed separately for each measure.

scripts/build-data.mjs bundles these files into data/js/ for the page; it reads
the 12-month frames and the world totals, and the page re-ranks from there.

Run from the project root:  python -m scripts.processing.build_app_data [monthly.csv(.gz)]
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from scripts._bootstrap import PROJECT_ROOT
from ingestion.eurostat_api import NOT_COUNTRIES
from project_paths import ASSETS_DIR, DERIVED_DATA_DIR, PROCESSED_DATA_DIR

N_KEEP = 25       # partners / products stored per frame (20 shown + a few to slide in)
N_CAND = 40       # candidates per product/flow, from yearly rankings
SRC = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else PROCESSED_DATA_DIR / "lu_trade_hs2_monthly.csv.gz"
OUT_DIR = DERIVED_DATA_DIR
(OUT_DIR / "products").mkdir(parents=True, exist_ok=True)

# WORLD rows carry the totals every share is computed against, so they stay in.
DROP_PARTNERS = NOT_COUNTRIES - {"WORLD"}
# measure -> (source column, divisor to the stored unit, decimals kept)
MEASURES = {
    "quantity": ("QUANTITY_IN_100KG", 1e4, 2),   # 100 kg -> thousand tonnes (0.01 kt = 10 t)
    "value":    ("VALUE_IN_EUROS",    1e6, 3),   # EUR -> million EUR (0.001 = EUR 1,000)
}


def sentence(x):
    return x[:1].upper() + x[1:].lower()


def num(v, digits=2):
    """Round, and write whole numbers without '.0' to keep the JSON small."""
    v = round(float(v), digits)
    return int(v) if v.is_integer() else v


def dumps(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


# ---- 1. Load ----------------------------------------------------------------
# keep_default_na=False: partner code "NA" is Namibia, not a missing value
raw = pd.read_csv(SRC, dtype=str, keep_default_na=False,
                  usecols=["time", "partner", "partner_label", "product", "product_label", "flow",
                           "QUANTITY_IN_100KG", "VALUE_IN_EUROS"])
for col, _, _ in MEASURES.values():
    raw[col] = pd.to_numeric(raw[col].replace("", np.nan))
raw["t"] = raw["time"].str[:4].astype(int) * 12 + raw["time"].str[5:7].astype(int) - 1

# Latest month available for both flows (totals), so frames are comparable.
tot = raw[(raw["partner"] == "WORLD") & (raw["product"] == "TOTAL")]
last_t = int(tot.groupby("flow")["t"].max().min())
first_t = 1999 * 12
raw = raw[(raw["t"] <= last_t) & ~raw["partner"].isin(DROP_PARTNERS)]
frames_t = np.arange(first_t + 11, last_t + 1)            # first full 12-month window: Dec 1999
frame_lab = [f"{t // 12}-{t % 12 + 1:02d}" for t in frames_t]
L = last_t - first_t + 1                                  # months in the grid

names = (raw[["partner", "partner_label"]].drop_duplicates("partner")
         .assign(name=lambda x: x["partner_label"].str.replace(r"\s*\(.*$", "", regex=True))
         .set_index("partner")["name"])
names["GB"], names["US"] = "United Kingdom", "United States"
names["LU"] = "Luxembourg"            # never a partner of itself, but the reporter the map centres on

products = raw[["product", "product_label"]].drop_duplicates("product").sort_values("product")
products["short"] = products["product_label"].str.replace(r"\s*;.*$", "", regex=True).map(sentence)
products.loc[products["product"] == "TOTAL", "short"] = "All goods"
labels = json.loads((ASSETS_DIR / "hs2_labels.json").read_text(encoding="utf-8"))


def add_rank(df, keys, tie):
    """Rank by v12 (descending) within keys; ties broken by `tie` order. Adds prev_rank (a year earlier)."""
    df = df.sort_values(keys + ["v12", tie], ascending=[True] * len(keys) + [False, True], kind="stable")
    df["rank"] = df.groupby(keys).cumcount() + 1
    prev = df[keys[:-1] + [tie, "t", "rank"]].rename(columns={"rank": "prev_rank"})
    prev["t"] += 12
    df = df.merge(prev, on=keys[:-1] + [tie, "t"], how="left")
    df["prev_rank"] = df["prev_rank"].fillna(0).astype(int)
    return df


# ---- 2. Rolling 12-month totals, per measure --------------------------------
def rolling_totals(col, divisor):
    """Return (m, world): 12-month totals per product/flow/partner/month in the stored unit."""
    d = raw.loc[raw[col].notna(), ["product", "flow", "partner", "t"]].copy()
    d["v"] = raw.loc[raw[col].notna(), col] / divisor
    # Only partners that rank in a product/flow's yearly top N_CAND can reach a
    # monthly top 25, so the full month grid is only built for those candidates.
    d["year"] = d["t"] // 12
    yearly = d[d["partner"] != "WORLD"].groupby(["product", "flow", "partner", "year"])["v"].sum().reset_index()
    yearly = yearly.sort_values(["product", "flow", "year", "v"], ascending=[True, True, True, False], kind="stable")
    yearly["r"] = yearly.groupby(["product", "flow", "year"]).cumcount() + 1
    cand = (pd.concat([yearly.loc[yearly["r"] <= N_CAND, ["product", "flow", "partner"]],
                       d.loc[d["partner"] == "WORLD", ["product", "flow", "partner"]]])
            .drop_duplicates().sort_values(["product", "flow", "partner"]).reset_index(drop=True))

    monthly = d.groupby(["product", "flow", "partner", "t"])["v"].sum()
    grid = cand.loc[cand.index.repeat(L)].reset_index(drop=True)
    grid["t"] = np.tile(np.arange(first_t, last_t + 1), len(cand))
    vals = monthly.reindex(pd.MultiIndex.from_frame(grid)).fillna(0).to_numpy()

    # rolling 12-month sum per series (grid rows are complete and ordered by t)
    cs = np.cumsum(vals.reshape(len(cand), L), axis=1)
    roll = cs[:, 11:] - np.concatenate([np.zeros((len(cand), 1)), cs[:, :-12]], axis=1)
    m = cand.loc[cand.index.repeat(len(frames_t))].reset_index(drop=True)
    m["t"] = np.tile(frames_t, len(cand))
    m["v12"] = np.round(roll.reshape(-1), 9)            # drop float noise from the cumulative sums

    # Any real trade counts; v12 was rounded above, so exact zeros are really zero.
    world = m[m["partner"] == "WORLD"].copy()
    m = m[(m["partner"] != "WORLD") & (m["v12"] > 1e-7)].copy()
    m = add_rank(m, ["product", "flow", "t"], "partner")
    m = m.sort_values(["product", "flow", "partner", "t"]).reset_index(drop=True)
    return m, world


# ---- 3. Rankings per product and measure ------------------------------------
def build_measure(col, divisor, digits):
    m, world = rolling_totals(col, divisor)
    m_by_product = dict(tuple(m.groupby("product", sort=False)))
    world_by_product = dict(tuple(world.groupby("product", sort=False)))

    def series_of(df):
        s = df.set_index("t")["v12"].reindex(frames_t).fillna(0)
        return [num(v, digits) for v in s.to_numpy()]

    def flow_blob(mp, wp, fl):
        k = mp[mp["flow"] == fl]
        if k.empty:
            return None
        top = k[k["rank"] <= N_KEEP]
        top20 = top[(top["t"] == last_t) & (top["rank"] <= 20)].sort_values("rank")["partner"].tolist()
        ever20 = list(dict.fromkeys(top20 + top.loc[top["rank"] <= 20, "partner"].tolist()))
        by_t = {t: g.sort_values("rank") for t, g in top.groupby("t")}
        k_by_p = dict(tuple(k.groupby("partner")))
        return {
            "world": series_of(wp[wp["flow"] == fl]),
            "top20": top20,
            "series": {p: series_of(k_by_p[p]) for p in ever20},
            "frames": [[[p, num(v, digits), int(r)] for p, v, r in
                        zip(by_t[t]["partner"], by_t[t]["v12"], by_t[t]["prev_rank"])] if t in by_t else []
                       for t in frames_t],
        }

    def blob_for(code):
        mp = m_by_product.get(code, m.iloc[0:0])
        wp = world_by_product.get(code, world.iloc[0:0])
        return {"Exports": flow_blob(mp, wp, "Export"), "Imports": flow_blob(mp, wp, "Import")}

    return {code: blob_for(code) for code in products["product"]}


built = {name: build_measure(*spec) for name, spec in MEASURES.items()}

# ---- 4. One file per HS2 chapter --------------------------------------------
for p in (OUT_DIR / "products").glob("*.json"):
    p.unlink()
for code in products.loc[products["product"] != "TOTAL", "product"]:
    per_measure = {name: built[name][code] for name in MEASURES}
    if any(b["Exports"] is None or b["Imports"] is None for b in per_measure.values()):
        continue                                          # need both flows and both measures
    (OUT_DIR / "products" / f"{code}.json").write_text(dumps(per_measure), encoding="utf-8")
available = ["TOTAL"] + sorted(p.stem for p in (OUT_DIR / "products").glob("*.json"))

# ---- 5. app_data.json -------------------------------------------------------
pinfo = products.set_index("product")
data = {
    "frames": frame_lab,
    "names": {p: names[p] for p in names.index if p != "WORLD"},
    "products": [{"code": p, "name": pinfo.at[p, "short"],
                  "full": "All goods" if p == "TOTAL" else sentence(pinfo.at[p, "product_label"])}
                 for p in available],
    "hs2": {code: {"name": labels[code]["short"], "icon": labels[code]["icon"],
                   "full": sentence(pinfo.at[code, "product_label"])}
            for code in products["product"] if code in labels},
    "measures": {name: {"total": built[name]["TOTAL"]} for name in MEASURES},
}
(OUT_DIR / "app_data.json").write_text(dumps(data), encoding="utf-8")

size_mb = sum(p.stat().st_size for p in (OUT_DIR / "products").glob("*.json")) / 1e6
print(f"Wrote {OUT_DIR / 'app_data.json'} ({(OUT_DIR / 'app_data.json').stat().st_size / 1e6:.1f} MB; "
      f"{len(frames_t)} frames {frame_lab[0]}-{frame_lab[-1]}, {len(available)} products, "
      f"{len(data['names'])} countries) and {len(available) - 1} product files ({size_mb:.1f} MB)")
