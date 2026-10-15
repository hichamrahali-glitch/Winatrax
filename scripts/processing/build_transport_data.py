"""Build prepared transport data and a standalone transport page.

Measured : extra-EU trade by mode of transport (DS-059334, customs data).
Estimated: CO2 (tonnes CO2e, well-to-wheel) for all trade in the latest full year:

    CO2 = tonnes of goods x distance (km) x emission factor (g CO2e per tonne-km) / 1e6

  tonnes      : DS-045409 quantity per partner (all goods), the same totals as the rest of the site
  mode split  : extra-EU partners -> measured mode shares for that partner (DS-059334)
                EU partners       -> Luxembourg's inland freight modal split (tran_hv_frmod),
                                     because customs do not record the mode inside the EU (estimate)
  distance    : great-circle Luxembourg -> partner country centroid (assets/country_centroids.csv)
                road / rail / inland waterway x 1.2; air: great-circle;
                sea: truck Luxembourg -> Antwerp + great-circle Antwerp -> partner x 1.3
  factors     : GLEC Framework v3.1 defaults (assets/emission_factors_glec.csv)
  Post, fixed installations (pipelines, power lines), self-propelled goods and unknown
  mode are left out of the CO2 estimate; their share is reported on the page.

Inputs: data/raw/api_transport/* (07_), data/processed/lu_trade_hs2_annual.csv.gz (00_)
Run from the project root:  python -m scripts.processing.build_transport_data
"""
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from scripts._bootstrap import PROJECT_ROOT
from ingestion.eurostat_api import comext_parse
from project_paths import ASSETS_DIR, DERIVED_DATA_DIR, PROCESSED_DATA_DIR, RAW_DATA_DIR

RAW = RAW_DATA_DIR / "api_transport"
OUT = DERIVED_DATA_DIR / "transport_co2.html"
EU26 = ["AT", "BE", "BG", "CY", "CZ", "DE", "DK", "EE", "ES", "FI", "FR", "GR", "HR", "HU",
        "IE", "IT", "LT", "LV", "MT", "NL", "PL", "PT", "RO", "SE", "SI", "SK"]
NOT_COUNTRIES = {"WORLD", "EXT_EA", "EXT_EA21", "EXT_EU", "EXT_EU27_2020", "INT_EA", "INT_EA21",
                 "INT_EU", "INT_EU27_2020", "QQ", "QR", "QS", "QU", "QV", "QW", "QX", "QY", "QZ", "XC", "XL"}
MODES = {"1": "sea", "2": "rail", "3": "road", "4": "air", "8": "inland_waterway",
         "0": "other", "5": "other", "7": "other", "9": "other"}       # other = left out of CO2
CO2_MODES = ["road", "rail", "inland_waterway", "sea", "air"]
FLOWS = {"1": "Imports", "2": "Exports"}
CODE_ALIAS = {"XS": "RS", "XM": "ME", "EL": "GR"}                   # Comext codes -> centroid codes
DETOUR_LAND, DETOUR_SEA = 1.2, 1.3
LUX = (49.6116, 6.1319)                                             # Luxembourg City
ANTWERP = (51.2194, 4.4025)


def gc_km(a, b):
    """Great-circle distance in km."""
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(h))


# ---- inputs -----------------------------------------------------------------
factors = pd.read_csv(ASSETS_DIR / "emission_factors_glec.csv").set_index("mode")
EF = factors["factor_g_co2e_per_tkm"].to_dict()
cent = pd.read_csv(ASSETS_DIR / "country_centroids.csv", keep_default_na=False).set_index("code")
road_to_antwerp = DETOUR_LAND * gc_km(LUX, ANTWERP)

def countries_only(df):
    # DS-059334 also has an "EXT_EU" row that equals the sum of all non-EU partners:
    # keep 2-letter country codes only, or every total would be counted twice.
    return df[df["partner"].str.fullmatch(r"[A-Z]{2}") & ~df["partner"].isin(NOT_COUNTRIES)].copy()


modes_all = countries_only(comext_parse(RAW / "lu_modes_total.json"))
modes_all["mode"] = modes_all["transport_mode"].map(MODES)
modes_all["flow"] = modes_all["flow"].map(FLOWS)
# Same rule as 07_: the time dimension ends with the running (partial) year
years = sorted(json.loads((RAW / "lu_modes_total.json").read_text())["dimension"]["time"]["category"]["index"])
YEAR = years[-2]

trade = pd.read_csv(PROCESSED_DATA_DIR / "lu_trade_hs2_annual.csv.gz", dtype=str, keep_default_na=False)
trade = trade[(trade["product"] == "TOTAL") & (trade["time"] == YEAR) & ~trade["partner"].isin(NOT_COUNTRIES)]
trade["t"] = pd.to_numeric(trade["QUANTITY_IN_100KG"].replace("", np.nan)).fillna(0) / 10   # 100 kg -> t
trade["flow"] = trade["flow"].map({"Import": "Imports", "Export": "Exports"})
names = trade.drop_duplicates("partner").set_index("partner")["partner_label"].str.replace(r"\s*\(.*$", "", regex=True)

split = comext_parse(RAW / "modal_split.json", labels=False)
split_year = split["time"].max()
s = split[split["time"] == split_year].set_index("tra_mode")["value"]
eu_split = {"road": s["ROAD"], "rail": s["RAIL"], "inland_waterway": s["IWW"]}
eu_split = {k: v / sum(eu_split.values()) for k, v in eu_split.items()}

# measured mode shares per extra-EU partner (by weight), latest year
mq = modes_all[(modes_all["time"] == YEAR) & (modes_all["indicators"] == "QUANTITY_KG")]
mode_t = mq.groupby(["partner", "flow", "mode"])["value"].sum().unstack("mode").fillna(0)
overall_extra = mq.groupby(["flow", "mode"])["value"].sum().unstack("mode").fillna(0)


def shares(row):
    tot = row.sum()
    return (row / tot).to_dict() if tot > 0 else None


# ---- 1. estimated CO2 per partner, flow and mode -----------------------------
rows, no_centroid = [], 0.0
for r in trade.itertuples():
    p, fl, tonnes = r.partner, r.flow, r.t
    if tonnes <= 0:
        continue
    code = CODE_ALIAS.get(p, p)
    if code not in cent.index:
        no_centroid += tonnes
        continue
    dest = (cent.at[code, "lat"], cent.at[code, "lon"])
    d = gc_km(LUX, dest)
    if p in EU26:
        sh, source = eu_split, "estimated"
    else:
        sh = shares(mode_t.loc[(p, fl)]) if (p, fl) in mode_t.index else None
        sh = sh or shares(overall_extra.loc[fl])
        source = "measured"
    for mode, share in sh.items():
        t_mode = tonnes * share
        if t_mode <= 0:
            continue
        if mode in ("road", "rail", "inland_waterway"):
            km, ef = DETOUR_LAND * d, EF[mode]
            co2 = t_mode * km * ef / 1e6
        elif mode == "air":
            km = d
            ef = EF["air_short_haul"] if d < 1500 else EF["air_long_haul"]
            co2 = t_mode * km * ef / 1e6
        elif mode == "sea":
            sea_km = DETOUR_SEA * gc_km(ANTWERP, dest)
            km, ef = road_to_antwerp + sea_km, EF["sea"]
            co2 = (t_mode * sea_km * EF["sea"] + t_mode * road_to_antwerp * EF["road"]) / 1e6
        else:                                                       # post, pipelines, self-propelled, unknown
            km, co2 = 0, 0.0
        rows.append({"partner": p, "flow": fl, "mode": mode, "source": source,
                     "tonnes": t_mode, "km": km, "tkm": t_mode * km, "co2": co2})
est = pd.DataFrame(rows)

# ---- 2. extra-EU products (HS2): CO2 from the customs quantities directly ----
prod = countries_only(pd.concat([comext_parse(f) for f in sorted(RAW.glob(f"lu_modes_hs2_{YEAR}_*.json"))],
                                ignore_index=True))
prod = prod[prod["indicators"] == "QUANTITY_KG"].copy()
prod["mode"] = prod["transport_mode"].map(MODES)
prod["flow"] = prod["flow"].map(FLOWS)
prod["tonnes"] = prod["value"] / 1000


def co2_row(p, mode, tonnes):
    code = CODE_ALIAS.get(p, p)
    if code not in cent.index or mode not in CO2_MODES:
        return 0.0
    dest = (cent.at[code, "lat"], cent.at[code, "lon"])
    d = gc_km(LUX, dest)
    if mode == "air":
        return tonnes * d * (EF["air_short_haul"] if d < 1500 else EF["air_long_haul"]) / 1e6
    if mode == "sea":
        return tonnes * (DETOUR_SEA * gc_km(ANTWERP, dest) * EF["sea"] + road_to_antwerp * EF["road"]) / 1e6
    return tonnes * DETOUR_LAND * d * EF[mode] / 1e6


prod["co2"] = [co2_row(p, m, t) for p, m, t in zip(prod["partner"], prod["mode"], prod["tonnes"])]
labels = pd.read_csv(ASSETS_DIR / "hs2_labels.csv", dtype=str, keep_default_na=False).set_index("code")


def r1(x):
    return round(float(x), 1)


def by_mode(df, value):
    g = df.groupby("mode")[value].sum()
    return {m: r1(g.get(m, 0)) for m in CO2_MODES + ["other"]}


summary = {}
for fl in ("Exports", "Imports", "Both"):
    e = est if fl == "Both" else est[est["flow"] == fl]
    summary[fl] = {
        "all": {"tonnes": by_mode(e, "tonnes"), "co2": by_mode(e, "co2"), "tkm": by_mode(e, "tkm")},
        "eu": {"tonnes": by_mode(e[e["source"] == "estimated"], "tonnes"),
               "co2": by_mode(e[e["source"] == "estimated"], "co2")},
        "extra": {"tonnes": by_mode(e[e["source"] == "measured"], "tonnes"),
                  "co2": by_mode(e[e["source"] == "measured"], "co2")},
        "partners": [
            {"code": p, "name": names.get(p, p), "eu": p in EU26,
             "tonnes": r1(g["tonnes"].sum()), "co2": r1(g["co2"].sum()),
             "byMode": {m: r1(g.loc[g["mode"] == m, "co2"].sum()) for m in CO2_MODES}}
            for p, g in sorted(e.groupby("partner"), key=lambda kv: -kv[1]["co2"].sum())[:15]],
    }
    pr = prod if fl == "Both" else prod[prod["flow"] == fl]
    top_p = pr.groupby("product")["co2"].sum().sort_values(ascending=False).head(12)
    summary[fl]["products"] = [
        {"code": c, "name": labels.at[c, "short"] if c in labels.index else c,
         "icon": labels.at[c, "icon"] if c in labels.index else "",
         "tonnes": r1(pr.loc[pr["product"] == c, "tonnes"].sum()), "co2": r1(v),
         "byMode": {m: r1(pr.loc[(pr["product"] == c) & (pr["mode"] == m), "co2"].sum()) for m in CO2_MODES}}
        for c, v in top_p.items()]

# measured modal split over time (extra-EU, all partners)
trend = {}
for fl in ("Exports", "Imports"):
    trend[fl] = {}
    for ind, key, div in (("VALUE_EUR", "value", 1e6), ("QUANTITY_KG", "tonnes", 1e3)):
        x = modes_all[(modes_all["flow"] == fl) & (modes_all["indicators"] == ind)]
        g = x.groupby(["time", "mode"])["value"].sum().unstack("mode").reindex(years[:-1]).fillna(0) / div
        trend[fl][key] = {m: [r1(v) for v in g.get(m, pd.Series(0, index=g.index))] for m in CO2_MODES + ["other"]}

# context: Luxembourg airport freight, CO2 of the air transport sector
air = comext_parse(RAW / "airport_freight.json", labels=False).set_index("time")["value"]
acc = comext_parse(RAW / "co2_by_activity.json", labels=False)
acc_year = acc.loc[acc["nace_r2"] == "H51", "time"].max()
a = acc[acc["time"] == acc_year].set_index("nace_r2")["value"]
own_air = mq[mq["mode"] == "air"]["value"].sum() / 1000                     # t, both flows, customs data
context = {
    "airport": {"year": max(y for y in air.index if y <= YEAR), "tonnes": None},
    "own_air_tonnes": r1(own_air),
    "co2_accounts": {"year": acc_year, "total": float(a.get("TOTAL", np.nan)), "air_transport": float(a.get("H51", np.nan)),
                     "land_transport": float(a.get("H49", np.nan))},
}
context["airport"]["tonnes"] = float(air[context["airport"]["year"]])

data = {
    "year": YEAR, "years": years[:-1], "modes": CO2_MODES + ["other"],
    "summary": summary, "trend": trend, "context": context,
    "split": {"year": split_year, "shares": {k: round(v, 3) for k, v in eu_split.items()}},
    "factors": [{"mode": m, "factor": float(f.factor_g_co2e_per_tkm), "basis": f.basis,
                 "ref": f.glec_reference, "note": f.note} for m, f in factors.iterrows()],
    "assumptions": {"detour_land": DETOUR_LAND, "detour_sea": DETOUR_SEA, "road_to_antwerp_km": round(road_to_antwerp),
                    "tonnes_without_centroid": r1(no_centroid)},
}

# Same data as JSON for the Streamlit app (app.py)
DERIVED_DATA_DIR.mkdir(parents=True, exist_ok=True)
(DERIVED_DATA_DIR / "transport_data.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

template = (ASSETS_DIR / "transport_template.html").read_text(encoding="utf-8")
marker = "/*__DATA__*/null"
assert template.count(marker) == 1
OUT.write_text(template.replace(marker, json.dumps(data, ensure_ascii=False, separators=(",", ":"))), encoding="utf-8")

tot = summary["Both"]["all"]
print(f"Wrote {OUT} ({YEAR}). Estimated CO2: {sum(tot['co2'].values()) / 1000:,.0f} kt CO2e; "
      f"air = {tot['tonnes']['air'] / sum(tot['tonnes'].values()):.2%} of tonnes, "
      f"{tot['co2']['air'] / sum(tot['co2'].values()):.1%} of CO2")
