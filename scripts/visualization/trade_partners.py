"""Who are Luxembourg's main trading partners, and how have they evolved? (by value)

Data  : Prepared monthly and annual Comext tables in data/processed/.
Output: data/derived/fig1_partners_rolling12m.png  (12-month rolling value)
        data/derived/fig2_partner_shares.png       (share of total by year)
        data/derived/lu_trade_partners_total.csv   (tidy monthly data)

Run from the project root:  python -m scripts.visualization.trade_partners
"""
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

from scripts._bootstrap import PROJECT_ROOT
from ingestion.eurostat_api import AGGREGATES
from project_paths import DERIVED_DATA_DIR, PROCESSED_DATA_DIR
from visualization.charts import chart_style as cs

DERIVED_DATA_DIR.mkdir(parents=True, exist_ok=True)
N_TOP = 6  # top partners shown per flow (by value in the latest full year)


def tidy(df):
    df["flow"] = df["flow"].map({"Import": "Imports", "Export": "Exports"})
    df["partner_label"] = df["partner_label"].str.replace(r"\s*\(.*$", "", regex=True)
    df.loc[df["partner"] == "GB", "partner_label"] = "United Kingdom"
    df["value"] = pd.to_numeric(df["VALUE_IN_EUROS"], errors="coerce")
    df["bn"] = df["value"] / 1e9
    return df


monthly = pd.read_csv(PROCESSED_DATA_DIR / "lu_trade_hs2_monthly.csv.gz", dtype=str, keep_default_na=False)
annual = pd.read_csv(PROCESSED_DATA_DIR / "lu_trade_hs2_annual.csv.gz", dtype=str, keep_default_na=False)
monthly = tidy(monthly[monthly["product"] == "TOTAL"].copy())
annual = tidy(annual[annual["product"] == "TOTAL"].copy())
monthly["date"] = pd.to_datetime(monthly["time"] + "-01")
annual["year"] = annual["time"].astype(int)
monthly[["time", "flow", "partner", "partner_label", "value"]].to_csv(
    DERIVED_DATA_DIR / "lu_trade_partners_total.csv", index=False)

# Keep months published for both flows (latest month can be partial).
last_month = monthly[monthly["partner"] == "WORLD"].groupby("flow")["date"].max().min()
monthly = monthly[monthly["date"] <= last_month]
countries_m = monthly[~monthly["partner"].isin(AGGREGATES)]
countries_a = annual[~annual["partner"].isin(AGGREGATES)]
last_year = annual.loc[annual["partner"] == "WORLD", "year"].max()

# ---- Which partners to show ------------------------------------------------
latest = countries_a[countries_a["year"] == last_year]
top = latest.sort_values("value", ascending=False).groupby("flow").head(N_TOP)
order_by_size = (latest[latest["partner_label"].isin(top["partner_label"])]
                 .groupby("partner_label")["value"].sum().sort_values(ascending=False).index.tolist())
assert len(order_by_size) <= len(cs.PALETTE)
cols = dict(zip(order_by_size, cs.PALETTE))

source_note = ("Source: Eurostat Comext DS-045409 (API), reporter = Luxembourg, product = total goods, "
               "value in EUR. Partner = country of origin (imports) / destination (exports).")
cs.setup()

# ---- Figure 1: 12-month rolling value (monthly data) -----------------------
full = pd.date_range(countries_m["date"].min(), last_month, freq="MS")
first_of_last12 = last_month - pd.DateOffset(months=11)
fig, axes = plt.subplots(2, 1, figsize=(11, 8), dpi=200)
fig.subplots_adjust(left=0.07, right=0.82, top=0.83, bottom=0.08, hspace=0.28)
for ax, fl in zip(axes, ["Exports", "Imports"]):
    shown = top[top["flow"] == fl]["partner_label"].tolist()
    last12 = (countries_m[(countries_m["flow"] == fl) & (countries_m["date"] >= first_of_last12)]
              .groupby("partner_label")["bn"].sum().sort_values(ascending=False))
    rank = {p: i + 1 for i, p in enumerate(last12.index)}
    ends = {}
    for p in shown:
        s = (countries_m[(countries_m["flow"] == fl) & (countries_m["partner_label"] == p)]
             .set_index("date")["bn"].reindex(full, fill_value=0).rolling(12).sum().dropna())
        ax.plot(s.index, s.values, color=cols[p], lw=1.6)
        ax.plot(s.index[-1], s.values[-1], "o", color=cols[p], ms=4)
        ends[p] = s.values[-1]
    ymax = ax.get_ylim()[1]
    names = list(ends)
    ys = cs.dodge([ends[p] for p in names], 0.06 * ymax)
    for p, y in zip(names, ys):
        ax.annotate(f"#{rank.get(p, '?')} {p}", (last_month, y), xytext=(10, 0),
                    textcoords="offset points", va="center", fontsize=9.5, color=cs.INK,
                    annotation_clip=False)
    ax.set_ylim(0, None)
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0f} bn")
    ax.xaxis.set_major_locator(mdates.YearLocator(2))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.set_title(fl, loc="left", fontweight="bold", fontsize=12)
cs.titles(fig, "Luxembourg's goods trade is dominated by its neighbours",
          f"Value of trade over the previous 12 months, EUR, top {N_TOP} partners per flow in {last_year}.\n"
          f"Labels show rank among all partner countries, 12 months to {last_month:%b %Y}.",
          source_note)
fig.savefig(DERIVED_DATA_DIR / "fig1_partners_rolling12m.png")
plt.close(fig)

# ---- Figure 2: share of total trade, by year -------------------------------
world_a = annual[annual["partner"] == "WORLD"].set_index(["year", "flow"])["value"]
grp = countries_a.assign(group=countries_a["partner_label"].where(
    countries_a["partner_label"].isin(order_by_size), "Rest of world"))
shares = grp.groupby(["year", "flow", "group"])["value"].sum().unstack("group").fillna(0)
shares = shares.div(world_a.reindex(shares.index), axis=0)
layers = order_by_size + ["Rest of world"]
colours = [cols[p] for p in order_by_size] + ["#d3d1c7"]

fig, axes = plt.subplots(1, 2, figsize=(11, 5.5), dpi=200, sharey=True)
fig.subplots_adjust(left=0.06, right=0.98, top=0.80, bottom=0.22, wspace=0.08)
for ax, fl in zip(axes, ["Exports", "Imports"]):
    s = shares.xs(fl, level="flow").reindex(columns=layers, fill_value=0)
    s = s[s.index <= last_year]
    ax.stackplot(s.index, s.T.values, colors=colours, edgecolor=cs.SURFACE, linewidth=0.3)
    ax.set_xlim(s.index.min(), s.index.max())
    ax.set_ylim(0, 1)
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0%}")
    ax.grid(False)
    ax.set_title(fl, loc="left", fontweight="bold", fontsize=12)
handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in colours]
fig.legend(handles, layers, loc="lower center", ncol=4, frameon=False, bbox_to_anchor=(0.5, 0.06))
cs.titles(fig, "How concentrated is Luxembourg's trade?",
          f"Share of total goods trade by partner, {shares.index.get_level_values('year').min()}-{last_year}",
          source_note)
fig.savefig(DERIVED_DATA_DIR / "fig2_partner_shares.png")
plt.close(fig)
print(f"Done. Latest month: {last_month:%b %Y}; latest full year: {last_year}")
