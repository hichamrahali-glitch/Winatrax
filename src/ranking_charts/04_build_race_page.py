"""Interactive page: Luxembourg's main trading partners and product groups,
by quantity (tonnes) or value (EUR) - bar chart races and line chart races,
for all goods or one HS2 product group.

Input : data/processed/lu_trade_hs2_monthly.csv.gz (run python/00_download_eurostat.py)
        assets/race_template.html, assets/hs2_labels.csv
Output: output/top20_race.html         page; all goods data embedded
        output/products/<code>.json    one file per HS2 chapter, loaded on demand
        output/flags/<code>.png        country flags (flagcdn.com, cached in data/flags)

Each frame is the total over the previous 12 months. Two measures are built:
  quantity: QUANTITY_IN_100KG, stored in thousand tonnes
  value   : VALUE_IN_EUROS,    stored in million EUR
Rankings are computed separately for each measure. The product filter needs
the page to be served (python3 -m http.server --directory output); opened as a
file, only "All goods" is available.

Run from the project root:  python python/04_build_race_page.py
"""
import json
import shutil
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

from eurostat_api import comext_parse
from trade_tree import KEEP_MAX, KEEP_MIN, KEEP_SHARE, partner_detail

N_KEEP = 25       # partners / products stored per frame (20 shown + a few to slide in)
N_CAND = 40       # candidates per product/flow, from yearly rankings
N_PROD_LINES = 15 # product groups in the products line race
FLAG_DIR = Path("data/flags")
OUT_DIR = Path("output")
(OUT_DIR / "products").mkdir(parents=True, exist_ok=True)
(OUT_DIR / "flags").mkdir(parents=True, exist_ok=True)
FLAG_DIR.mkdir(parents=True, exist_ok=True)

NOT_COUNTRIES = {"EXT_EA", "EXT_EA21", "EXT_EU", "EXT_EU27_2020", "INT_EA", "INT_EA21",
                 "INT_EU", "INT_EU27_2020", "QQ", "QR", "QS", "QU", "QV", "QW",
                 "QX", "QY", "QZ", "XC", "XL"}
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
raw = pd.read_csv("data/processed/lu_trade_hs2_monthly.csv.gz", dtype=str, keep_default_na=False,
                  usecols=["time", "partner", "partner_label", "product", "product_label", "flow",
                           "QUANTITY_IN_100KG", "VALUE_IN_EUROS"])
for col, _, _ in MEASURES.values():
    raw[col] = pd.to_numeric(raw[col].replace("", np.nan))
raw["t"] = raw["time"].str[:4].astype(int) * 12 + raw["time"].str[5:7].astype(int) - 1

# Latest month available for both flows (totals), so frames are comparable.
tot = raw[(raw["partner"] == "WORLD") & (raw["product"] == "TOTAL")]
last_t = int(tot.groupby("flow")["t"].max().min())
first_t = 1999 * 12
raw = raw[(raw["t"] <= last_t) & ~raw["partner"].isin(NOT_COUNTRIES)]
frames_t = np.arange(first_t + 11, last_t + 1)            # first full 12-month window: Dec 1999
frame_lab = [f"{t // 12}-{t % 12 + 1:02d}" for t in frames_t]
L = last_t - first_t + 1                                  # months in the grid

names = (raw[["partner", "partner_label"]].drop_duplicates("partner")
         .assign(name=lambda x: x["partner_label"].str.replace(r"\s*\(.*$", "", regex=True))
         .set_index("partner")["name"])
names["GB"], names["US"] = "United Kingdom", "United States"
names["LU"] = "Luxembourg"            # never a partner of itself, but a reporter in the country comparison

products = raw[["product", "product_label"]].drop_duplicates("product").sort_values("product")
products["short"] = products["product_label"].str.replace(r"\s*;.*$", "", regex=True).map(sentence)
products.loc[products["product"] == "TOTAL", "short"] = "All goods"
labels = pd.read_csv("assets/hs2_labels.csv", dtype=str, keep_default_na=False, encoding="utf-8")


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


# ---- 3. Page data per measure -----------------------------------------------
used_partners = set()


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
        b = {"Exports": flow_blob(mp, wp, "Export"), "Imports": flow_blob(mp, wp, "Import")}
        for f in b.values():
            if f:
                used_partners.update(f["series"])
                used_partners.update(e[0] for fr in f["frames"] for e in fr)
        return b

    blobs = {code: blob_for(code) for code in products["product"]}

    # Product race: main product groups and their main partner. For each flow
    # and month: the top product groups (12-month total, from the WORLD rows),
    # their rank a year earlier, and the partner with the largest share of that
    # product (shown as a flag on a pole in the page).
    pw = world[(world["product"] != "TOTAL") & (world["v12"] > 1e-7)].copy()
    pw = add_rank(pw, ["flow", "t"], "product")
    lead = m.loc[m["rank"] == 1, ["product", "flow", "t", "partner", "v12"]].rename(
        columns={"partner": "lead", "v12": "lead_v"})
    pw = pw.merge(lead, on=["product", "flow", "t"], how="left")
    pw["lead_share"] = np.where(pw["lead_v"].isna(), 0, np.round(pw["lead_v"] / pw["v12"], 3))
    pw["lead"] = pw["lead"].fillna("")
    used_partners.update(x for x in pw.loc[pw["rank"] <= N_KEEP, "lead"].unique() if x)
    ptop = pw[pw["rank"] <= N_KEEP]
    pw_by_p = dict(tuple(pw.groupby("product")))

    def prod_flow(fl):
        k = ptop[ptop["flow"] == fl]
        by_t = {t: g.sort_values("rank") for t, g in k.groupby("t")}
        wt = world[(world["product"] == "TOTAL") & (world["flow"] == fl)]
        # products line race: the latest top N_PROD_LINES groups, full series
        top_now = k[k["t"] == last_t].sort_values("rank")["product"].head(N_PROD_LINES).tolist()
        return {
            "total": series_of(wt),
            "top": top_now,
            "series": {p: series_of(pw_by_p[p][pw_by_p[p]["flow"] == fl]) for p in top_now},
            "frames": [[[p, num(v, digits), int(r), l, num(sh, 3)] for p, v, r, l, sh in
                        zip(g["product"], g["v12"], g["prev_rank"], g["lead"], g["lead_share"])]
                       if (g := by_t.get(t)) is not None else [] for t in frames_t],
        }

    return blobs, {"Exports": prod_flow("Export"), "Imports": prod_flow("Import")}


built = {name: build_measure(*spec) for name, spec in MEASURES.items()}

for p in (OUT_DIR / "products").glob("*.json"):
    p.unlink()
for code in products.loc[products["product"] != "TOTAL", "product"]:
    per_measure = {name: built[name][0][code] for name in MEASURES}
    if any(b["Exports"] is None or b["Imports"] is None for b in per_measure.values()):
        continue                                          # need both flows for the page
    (OUT_DIR / "products" / f"{code}.json").write_text(dumps(per_measure), encoding="utf-8")
available = ["TOTAL"] + sorted(p.stem for p in (OUT_DIR / "products").glob("*.json"))
prod_info = (products[products["product"] != "TOTAL"][["product", "product_label"]]
             .merge(labels.rename(columns={"code": "product"}), on="product", how="inner"))

# ---- 3c. Partner detail: product tree HS2 > HS4 > HS6 > CN8 ----------------
# From the per-partner downloads of 05_ (latest full year). At every level we
# keep the children that make up KEEP_SHARE of their parent (at least KEEP_MIN,
# at most KEEP_MAX); the rest is summed into "other". The page can collapse
# further with its slider, so only the most significant flows are shown.
CN8_DIR = Path("data/raw/api_cn8")
(OUT_DIR / "partners").mkdir(parents=True, exist_ok=True)
for p in (OUT_DIR / "partners").glob("*.json"):
    p.unlink()

partner_list = []
detail_year = None
for f in sorted(CN8_DIR.glob("*.json")):
    year, partner = f.stem.split("_", 1)
    detail_year = year
    df = comext_parse(f)
    if df is None:
        continue
    out = partner_detail(df, year)                  # shared with app.py (python/trade_tree.py)
    (OUT_DIR / "partners" / f"{partner}.json").write_text(dumps(out), encoding="utf-8")
    used_partners.add(partner)
    total_trade = out["value"]["Exports"]["v"] + out["value"]["Imports"]["v"]
    partner_list.append({"code": partner, "trade": num(total_trade, 1)})
partner_list.sort(key=lambda p: -p["trade"])

# Every other partner country with trade in that year: the page fetches these
# live from the Eurostat API when selected (it allows browser requests).
prepared = {p["code"] for p in partner_list}
ann = pd.read_csv("data/processed/lu_trade_hs2_annual.csv.gz", dtype=str, keep_default_na=False)
ann = ann[(ann["product"] == "TOTAL") & (ann["time"] == str(detail_year)) & ~ann["partner"].isin(NOT_COUNTRIES)
          & (ann["partner"] != "WORLD")]
ann["v"] = pd.to_numeric(ann["VALUE_IN_EUROS"].replace("", np.nan)).fillna(0) / 1e6
live_list = [{"code": c, "trade": num(v, 1)} for c, v in
             ann.groupby("partner")["v"].sum().sort_values(ascending=False).items()
             if c not in prepared and v > 0]
for p in live_list:
    used_partners.add(p["code"])

# ---- 3d. Country comparison: total trade of every EU reporter --------------
# From 06_: DS-045409 with partner = WORLD (all reporters) and demo_pjan
# population. Per-inhabitant figures and the EU average are computed in the page.
countries = None
trade_file, pop_file = Path("data/raw/api_countries/trade_totals.json"), Path("data/raw/api_countries/population.json")
if trade_file.exists() and pop_file.exists():
    tt = comext_parse(trade_file, labels=False)
    pop = comext_parse(pop_file, labels=False)
    tt = tt[tt["reporter"].str.fullmatch(r"[A-Z]{2}")]               # countries only (no EU/EA aggregates)
    lu = tt[(tt["reporter"] == "LU") & (tt["indicators"] == "VALUE_IN_EUROS")]
    years = sorted(lu.groupby("time")["flow"].nunique().loc[lambda x: x == 2].index)
    geo = {"GR": "EL"}                                                # population uses EL for Greece
    popv = pop.set_index(["geo", "time"])["value"]
    series = {}
    for code, g in tt.groupby("reporter"):
        entry = {}
        for name, (col, divisor, digits) in MEASURES.items():
            entry[name] = {}
            for fl_code, fl in (("2", "Exports"), ("1", "Imports")):
                x = g[(g["indicators"] == col) & (g["flow"] == fl_code)].set_index("time")["value"]
                entry[name][fl] = [num(x[y] / divisor, digits) if y in x.index else None for y in years]
        entry["pop"] = [int(popv[(geo.get(code, code), y)]) if (geo.get(code, code), y) in popv.index else None
                        for y in years]
        series[code] = entry
        used_partners.add(code)
    countries = {"years": years, "series": series,
                 "eu27": ["AT", "BE", "BG", "CY", "CZ", "DE", "DK", "EE", "ES", "FI", "FR", "GR", "HR", "HU",
                          "IE", "IT", "LT", "LU", "LV", "MT", "NL", "PL", "PT", "RO", "SE", "SI", "SK"]}

# ---- 4. Flags ---------------------------------------------------------------
FLAG_ALIASES = {"xs": "rs", "xm": "me", "xp": "ps", "el": "gr", "uk": "gb"}
have_flag = []
for code in sorted(used_partners):
    f = FLAG_DIR / f"{code.lower()}.png"
    if not f.exists():
        url = f"https://flagcdn.com/w80/{FLAG_ALIASES.get(code.lower(), code.lower())}.png"
        try:
            urllib.request.urlretrieve(url, f)
        except Exception:                                 # e.g. historical codes with no flag
            f.unlink(missing_ok=True)
            continue
    shutil.copyfile(f, OUT_DIR / "flags" / f.name)
    have_flag.append(code)

# ---- 5. Page ----------------------------------------------------------------
pinfo = products.set_index("product")
data = {
    "frames": frame_lab,
    "names": {p: names[p] for p in names.index if p in used_partners},
    "flags": {c: f"flags/{c.lower()}.png" for c in have_flag},
    "products": [{"code": p, "name": pinfo.at[p, "short"],
                  "full": "All goods" if p == "TOTAL" else sentence(pinfo.at[p, "product_label"])}
                 for p in available],
    "product": "TOTAL",
    "hs2": {r.product: {"name": r.short, "icon": r.icon, "full": sentence(r.product_label)}
            for r in prod_info.itertuples()},
    "measures": {name: {"total": built[name][0]["TOTAL"], "prodrace": built[name][1]} for name in MEASURES},
    "partnerDetail": {"year": detail_year, "list": partner_list, "live": live_list,
                      "keep": {"share": KEEP_SHARE, "min": KEEP_MIN, "max": KEEP_MAX}},
    "countries": countries,
}

# Same data as JSON for the Streamlit app (app.py)
(OUT_DIR / "app_data.json").write_text(dumps(data), encoding="utf-8")

template = Path("assets/race_template.html").read_text(encoding="utf-8")
marker = "/*__DATA__*/null"
assert template.count(marker) == 1
(OUT_DIR / "top20_race.html").write_text(template.replace(marker, dumps(data)), encoding="utf-8")

size_mb = sum(p.stat().st_size for p in (OUT_DIR / "products").glob("*.json")) / 1e6
page_mb = (OUT_DIR / "top20_race.html").stat().st_size / 1e6
part_mb = sum(p.stat().st_size for p in (OUT_DIR / "partners").glob("*.json")) / 1e6
print(f"Wrote output/top20_race.html ({page_mb:.1f} MB; {len(frames_t)} frames, {len(available)} products, "
      f"{len(have_flag)} flags; {size_mb:.1f} MB of product files; "
      f"{len(partner_list)} partner detail files, {part_mb:.1f} MB)")
