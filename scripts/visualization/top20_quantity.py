"""Who are Luxembourg's main trading partners, and how have they evolved?
Top 20 partners by quantity (weight), exports and imports, 1999 - latest.

Data  : Prepared monthly Comext table in data/processed/.
Chart : 12-month rolling total in million tonnes, linear axis. Top 20 = biggest
        partners over the latest 12 months. Top 5 in colour with flag, rank and
        tonnage at the line end; ranks 6-20 listed with flags on the right.
Output: data/derived/top20_exports_quantity.png
        data/derived/top20_imports_quantity.png
        data/derived/top20_quantity_rolling12m.csv

Run from the project root:  python -m scripts.visualization.top20_quantity
"""
import urllib.request
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.image as mpimg
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.offsetbox import AnnotationBbox, OffsetImage

from scripts._bootstrap import PROJECT_ROOT
from ingestion.eurostat_api import AGGREGATES
from project_paths import DERIVED_DATA_DIR, PROCESSED_DATA_DIR, RAW_DATA_DIR
from visualization.charts import chart_style as cs

N_TOP, N_COLOUR = 20, 5
FLAG_DIR = RAW_DATA_DIR / "flags"
FLAG_DIR.mkdir(parents=True, exist_ok=True)
DERIVED_DATA_DIR.mkdir(parents=True, exist_ok=True)

# ---- 1. Data ----------------------------------------------------------------
m = pd.read_csv(PROCESSED_DATA_DIR / "lu_trade_hs2_monthly.csv.gz", dtype=str, keep_default_na=False)
m = m[m["product"] == "TOTAL"].copy()

# Codes for secret / unspecified partners, which are not countries.
NOT_COUNTRIES = set(AGGREGATES) | {"QQ", "QR", "QS", "QU", "QV", "QW", "QX", "QY", "QZ", "XC", "XL"}
m["flow"] = m["flow"].map({"Import": "Imports", "Export": "Exports"})
m["date"] = pd.to_datetime(m["time"] + "-01")
m["mt"] = pd.to_numeric(m["QUANTITY_IN_100KG"], errors="coerce") / 1e7
m["name"] = m["partner_label"].str.replace(r"\s*\(.*$", "", regex=True)
m.loc[m["partner"] == "GB", "name"] = "United Kingdom"
m.loc[m["partner"] == "US", "name"] = "United States"

last_month = m[m["partner"] == "WORLD"].groupby("flow")["date"].max().min()
m = m[(m["date"] <= last_month) & ~m["partner"].isin(NOT_COUNTRIES)]
names = m.drop_duplicates("partner").set_index("partner")["name"]

# 12-month rolling totals on a complete month grid (missing months = 0)
months = pd.date_range("1999-01-01", last_month, freq="MS")
wide = m.pivot_table(index="date", columns=["flow", "partner"], values="mt", aggfunc="sum")
wide = wide.reindex(months).fillna(0)
roll = wide.rolling(12).sum().dropna()

latest = roll.iloc[-1]
top = {fl: latest[fl].sort_values(ascending=False).head(N_TOP) for fl in ("Exports", "Imports")}
rows = []
for fl, s in top.items():
    for rank, p in enumerate(s.index, start=1):
        for date, v in roll[(fl, p)].items():
            rows.append((fl, rank, p, names[p], f"{date:%Y-%m}", v))
pd.DataFrame(rows, columns=["flow", "rank", "partner", "name", "month", "mt_12m"]).to_csv(
    DERIVED_DATA_DIR / "top20_quantity_rolling12m.csv", index=False)

# ---- 2. Flags (flagcdn.com, cached in the repo) ----------------------------
FLAG_ALIASES = {"xs": "rs", "xm": "me", "xp": "ps", "el": "gr", "uk": "gb"}


def get_flag(code):
    f = FLAG_DIR / f"{code.lower()}.png"
    if not f.exists():
        urllib.request.urlretrieve(
            f"https://flagcdn.com/w80/{FLAG_ALIASES.get(code.lower(), code.lower())}.png", f)
    return mpimg.imread(f)


# ---- 3. Colours (follow the country, consistent across both charts) --------
both = pd.concat([top[fl].head(N_COLOUR) for fl in top])
coloured = both.groupby(level=0).sum().sort_values(ascending=False).index.tolist()
assert len(coloured) <= len(cs.PALETTE)
cols = dict(zip(coloured, cs.PALETTE))


def fmt_q(x):
    return f"{x:.1f} Mt" if x >= 0.1 else f"{x * 1000:.0f} kt"


TITLES = {
    "Exports": ("Where do Luxembourg's goods go?",
                "Goods exported from Luxembourg to its 20 biggest destinations"),
    "Imports": ("Where do Luxembourg's goods come from?",
                "Goods imported into Luxembourg from its 20 biggest suppliers"),
}
NOTES = {
    "Exports": ("\nNote: the 2000-2003 peaks for France and Belgium come from single product lines (plastics to "
                "France in 2001, mineral fuels to Belgium in 2002) and are likely recording anomalies in the source."),
    "Imports": "",
}

# ---- 4. One chart per flow -------------------------------------------------
cs.setup()
for fl in ("Exports", "Imports"):
    s = top[fl]
    fig = plt.figure(figsize=(14, 8.5), dpi=200)
    ax = fig.add_axes([0.05, 0.10, 0.55, 0.72])
    for rank, p in enumerate(s.index, start=1):
        y = roll[(fl, p)]
        if rank > N_COLOUR:
            ax.plot(y.index, y.values, color=cs.GREY, lw=0.8, zorder=1)
    for rank, p in enumerate(s.index[:N_COLOUR], start=1):
        y = roll[(fl, p)]
        ax.plot(y.index, y.values, color=cols[p], lw=2.2, zorder=3)
        ax.plot(y.index[-1], y.values[-1], "o", color=cols[p], ms=5, zorder=4)

    ymax = roll[fl][s.index].to_numpy().max() * 1.03
    ax.set_ylim(0, ymax)
    ax.set_xlim(roll.index[0], last_month)
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0f} Mt")
    ax.xaxis.set_major_locator(mdates.YearLocator(2))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

    # top 5: flag + label right at the line end (nudged apart if too close)
    big = list(s.index[:N_COLOUR])
    ys = cs.dodge([s[p] for p in big], ymax * 0.045)
    for p, y_lab in zip(big, ys):
        rank = big.index(p) + 1
        if abs(y_lab - s[p]) > ymax * 0.005:
            ax.annotate("", (last_month, s[p]), xytext=(18, (y_lab - s[p]) / ymax * 0.72 * 8.5 * 72),
                        textcoords="offset points", annotation_clip=False,
                        arrowprops=dict(arrowstyle="-", color=cols[p], lw=0.6))
        ax.add_artist(AnnotationBbox(OffsetImage(get_flag(p), zoom=0.22), (last_month, y_lab),
                                     xybox=(30, 0), boxcoords="offset points", frameon=False,
                                     annotation_clip=False))
        ax.annotate(f"{rank}. {names[p]}  {fmt_q(s[p])}", (last_month, y_lab), xytext=(46, 0),
                    textcoords="offset points", va="center", fontsize=10.5, fontweight="bold",
                    color=cs.INK, annotation_clip=False)

    # ranks 6-20: a ranked list in its own column
    fig.text(0.80, 0.80, "Also in the top 20 (grey lines)", fontsize=10.5, fontweight="bold", color=cs.INK_2)
    for i, p in enumerate(s.index[N_COLOUR:]):
        ytxt = 0.765 - i * 0.043
        flag_ax = fig.add_axes([0.80, ytxt - 0.011, 0.022, 0.022])
        flag_ax.imshow(get_flag(p)); flag_ax.axis("off")
        fig.text(0.827, ytxt, f"{N_COLOUR + i + 1}. {names[p]}  {fmt_q(s[p])}",
                 fontsize=9.5, color="#3d3d3a", va="center")

    cs.titles(fig, TITLES[fl][0],
              f"{TITLES[fl][1]}, by weight.\nEach point = total over the previous 12 months, in million tonnes (Mt). "
              f"Ranking for the 12 months to {last_month:%B %Y}.",
              "Source: Eurostat, international trade in goods (Comext DS-045409), all goods, quantity. "
              "1 Mt = 1 million tonnes; kt = thousand tonnes." + NOTES[fl])
    out = DERIVED_DATA_DIR / f"top20_{fl.lower()}_quantity.png"
    fig.savefig(out)
    plt.close(fig)
    print(f"Wrote {out}")
