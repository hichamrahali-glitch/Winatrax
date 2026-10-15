"""Seasonality of Luxembourg's trade: a typical year, and seasonality by product.

Used by the seasonality page. Data: data/derived/seasonality.json, written by
scripts/processing/build_seasonality_data.py.

Method (a simplified version of what Eurostat does with JDemetra+, TRAMO-SEATS):
1. Calendar: log(actual / centred 12-month trend) is regressed on 12 month dummies,
   the month's working days (Mon-Fri minus Luxembourg public holidays) and an Easter
   regressor (share of the 8 days before Easter Sunday in the month), both as
   deviations from their long-run average for that calendar month. Outliers
   (> 3 robust standard deviations) are dropped and the model refitted; a regressor
   is applied only if |t| >= 1.96.
2. Season: on the calendar-adjusted series, a month's seasonal factor in a given
   year is the median actual/trend ratio over the 7 nearest usable years, rescaled
   so the year averages 1. With "freeze" on, 2020-21 feed neither step.
"""
import json
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from project_paths import DERIVED_DATA_DIR

OUT = DERIVED_DATA_DIR
ABOVE, BELOW, INK, GRID = "#2a78d6", "#e34948", "#52514e", "#e5e4df"
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
MONTHS_LONG = ["January", "February", "March", "April", "May", "June", "July", "August",
               "September", "October", "November", "December"]
FROZEN_YEARS = (2020, 2021)


# ---- data -------------------------------------------------------------------
@st.cache_data
def load_seasonality():
    return json.loads((OUT / "seasonality.json").read_text(encoding="utf-8"))


@st.cache_data
def load_hs2_names():
    f = OUT / "app_data.json"
    return json.loads(f.read_text(encoding="utf-8"))["hs2"] if f.exists() else {}


def product_label(code, hs2):
    if code == "TOTAL":
        return "All goods"
    h = hs2.get(code)
    return f"{h['icon']} {h['name']}" if h else code


# ---- calendar ---------------------------------------------------------------
def easter(y):
    a, b, c = y % 19, y // 100, y % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    return date(y, (h + l - 7 * m + 114) // 31, (h + l - 7 * m + 114) % 31 + 1)


def lu_holidays(y):
    e = easter(y)
    days = {date(y, 1, 1), e + timedelta(1), date(y, 5, 1), e + timedelta(39), e + timedelta(50),
            date(y, 6, 23), date(y, 8, 15), date(y, 11, 1), date(y, 12, 25), date(y, 12, 26)}
    if y >= 2019:
        days.add(date(y, 5, 9))   # Europe Day
    return days


@st.cache_data
def calendar_regressors(months):
    """Working-day and Easter regressors, as deviations from each calendar month's mean."""
    wd, east = [], []
    for ym in months:
        y, mo = int(ym[:4]), int(ym[5:])
        hol, e = lu_holidays(y), easter(y)
        n = (date(y + mo // 12, mo % 12 + 1, 1) - date(y, mo, 1)).days
        days = [date(y, mo, d) for d in range(1, n + 1)]
        wd.append(sum(d.weekday() < 5 and d not in hol for d in days))
        east.append(sum((e - timedelta(k)).month == mo for k in range(1, 9)) / 8)
    wd, east = np.array(wd, float), np.array(east)
    mo = np.arange(len(months)) % 12
    dev = lambda x: x - np.array([x[mo == j].mean() for j in range(12)])[mo]
    return dev(wd), dev(east)


# ---- adjustment -------------------------------------------------------------
def trend_2x12(y):
    t = np.full(len(y), np.nan)
    w = np.r_[0.5, np.ones(11), 0.5] / 12
    for i in range(6, len(y) - 6):
        t[i] = w @ y[i - 6:i + 7]   # nan if any month is missing
    return t


def adjust(y, months, freeze):
    """y: monthly values (nan = missing). Returns seasonal factors per year and calendar fit."""
    n, y0 = len(y), int(months[0][:4])
    years = np.arange(n) // 12 + y0
    frozen = np.isin(years, FROZEN_YEARS) if freeze else np.zeros(n, bool)
    wd, east = calendar_regressors(tuple(months))

    # 1. calendar regression
    t0 = trend_2x12(y)
    ok = np.isfinite(y) & np.isfinite(t0) & (y > 0) & ~frozen
    X = np.column_stack([np.eye(12)[np.arange(n) % 12], wd, east])
    fit = {"wd": 0.0, "t_wd": 0.0, "easter": 0.0, "t_easter": 0.0}
    keep = ok.copy()
    for _ in range(2):
        if keep.sum() < 36:
            break
        z = np.log(y[keep] / t0[keep])
        beta, *_ = np.linalg.lstsq(X[keep], z, rcond=None)
        res = z - X[keep] @ beta
        s2 = res @ res / (keep.sum() - X.shape[1])
        se = np.sqrt(np.clip(np.diag(np.linalg.pinv(X[keep].T @ X[keep])) * s2, 0, None))
        fit = {"wd": beta[12], "t_wd": beta[12] / se[12] if se[12] else 0.0,
               "easter": beta[13], "t_easter": beta[13] / se[13] if se[13] else 0.0}
        mad = np.median(np.abs(res)) * 1.4826
        idx = np.flatnonzero(keep)
        keep[idx[np.abs(res) > 3 * mad]] = False
    fit["use_wd"], fit["use_easter"] = abs(fit["t_wd"]) >= 1.96, abs(fit["t_easter"]) >= 1.96
    cal = np.exp(fit["wd"] * wd * fit["use_wd"] + fit["easter"] * east * fit["use_easter"])

    # 2. seasonal factors on the calendar-adjusted series
    yc = y / cal
    ratio = yc / trend_2x12(yc)
    ny = int(np.ceil(n / 12))
    R = np.full(ny * 12, np.nan)
    R[:n] = ratio
    R = R.reshape(ny, 12)
    usable = [not (freeze and y0 + k in FROZEN_YEARS) for k in range(ny)]
    SF = np.ones((ny, 12))
    for k in range(ny):
        order = sorted(range(ny), key=lambda j: (abs(j - k), j))
        for mo in range(12):
            vals = [R[j, mo] for j in order if usable[j] and np.isfinite(R[j, mo])][:7]
            SF[k, mo] = np.median(vals) if vals else 1.0
        SF[k] /= SF[k].mean()
    return SF, fit


def profile(SF, y0, ya, yb):
    rows = SF[ya - y0:yb - y0 + 1]
    mean = rows.mean(axis=0)
    return {"mean": mean, "lo": rows.min(axis=0), "hi": rows.max(axis=0),
            "peak": int(mean.argmax()), "low": int(mean.argmin()), "swing": mean.max() - mean.min()}


@st.cache_data(show_spinner="Estimating seasonal factors…")
def season(product, flow, measure, freeze):
    D = load_seasonality()
    y = np.array([np.nan if v is None else v for v in D["series"][product][flow][measure]], float)
    SF, fit = adjust(y, D["months"], freeze)
    return SF, fit


@st.cache_data(show_spinner="Comparing products…")
def product_table(flow, measure, ya, yb, freeze, n=20):
    D = load_seasonality()
    months, y0 = D["months"], int(D["months"][0][:4])
    sel = [i for i, m in enumerate(months) if ya <= int(m[:4]) <= yb]
    size = {p: np.nansum([D["series"][p][flow]["value"][i] or 0 for i in sel])
            for p in D["series"] if p != "TOTAL" and flow in D["series"][p]}
    top = sorted(size, key=size.get, reverse=True)[:n]
    rows = []
    for p in ["TOTAL"] + top:
        SF, fit = season(p, flow, measure, freeze)
        pr = profile(SF, y0, ya, yb)
        rows.append({"code": p, "profile": [round((v - 1) * 100, 1) for v in pr["mean"]],
                     "swing": pr["swing"] * 100,
                     "peak": f"{MONTHS[pr['peak']]} {(pr['mean'][pr['peak']] - 1) * 100:+.0f}%",
                     "low": f"{MONTHS[pr['low']]} {(pr['mean'][pr['low']] - 1) * 100:+.0f}%",
                     "wd": (np.exp(fit["wd"]) - 1) * 100 if fit["use_wd"] else None})
    total, rest = rows[0], sorted(rows[1:], key=lambda r: -r["swing"])
    return [total] + rest


# ---- charts -----------------------------------------------------------------
def typical_year_figure(pr, ya, yb):
    d = (pr["mean"] - 1) * 100
    fig = go.Figure(go.Bar(
        x=MONTHS, y=d, marker_color=[ABOVE if v >= 0 else BELOW for v in d], marker_cornerradius=4,
        error_y=dict(type="data", symmetric=False, array=(pr["hi"] - pr["mean"]) * 100,
                     arrayminus=(pr["mean"] - pr["lo"]) * 100, color=INK, thickness=1.2, width=4),
        customdata=np.column_stack([(pr["lo"] - 1) * 100, (pr["hi"] - 1) * 100, MONTHS_LONG]),
        hovertemplate="<b>%{customdata[2]}</b><br>Average seasonal effect: %{y:+.1f}%"
                      "<br>Range across years: %{customdata[0]:+.0f}% to %{customdata[1]:+.0f}%<extra></extra>"))
    for i in (pr["peak"], pr["low"]):
        top = i == pr["peak"]
        fig.add_annotation(x=MONTHS[i], y=(pr["hi"][i] if top else pr["lo"][i]) * 100 - 100,
                           text=f"{d[i]:+.0f}%", showarrow=False, yshift=12 if top else -12,
                           font=dict(size=12, color=INK))
    fig.update_layout(height=360, margin=dict(l=10, r=10, t=10, b=10), showlegend=False, bargap=0.35,
                      plot_bgcolor="rgba(0,0,0,0)",
                      yaxis=dict(title="vs trend", ticksuffix="%", zeroline=True, zerolinecolor=INK,
                                 gridcolor=GRID),
                      xaxis=dict(title=None))
    return fig


# ---- section ----------------------------------------------------------------
def _pick_from_table():
    """Table row selected -> chart that product (runs before the rerun)."""
    sel = st.session_state["season_table"].selection.rows
    if sel:
        st.session_state["season_product"] = st.session_state["season_codes"][sel[0]]


def render():
    D, hs2 = load_seasonality(), load_hs2_names()
    y0, y1 = int(D["months"][0][:4]), int(D["months"][-1][:4])
    products = ["TOTAL"] + sorted(p for p in D["series"] if p != "TOTAL")

    st.subheader("When in the year does Luxembourg trade most?")
    st.caption("Monthly trade has a seasonal rhythm. These charts strip out working-day and Easter effects first, "
               "as Eurostat does, then measure how far each month typically sits above or below the trend.")

    c1, c2, c3, c4 = st.columns([1, 1, 2, 1.2])
    flow = c1.radio("Flow", ["Imports", "Exports"], horizontal=True, key="season_flow")
    measure = c2.radio("Measure", ["value", "quantity"], horizontal=True, key="season_measure",
                       format_func=lambda m: "Value (€)" if m == "value" else "Weight (t)")
    ya, yb = c3.slider("Years", y0, y1, (2010, y1 - 1), key="season_years")
    freeze = c4.toggle("Freeze factors in 2020–21", value=True, key="season_freeze",
                       help="Keep the pandemic collapse and rebound out of the seasonal estimates, "
                            "as Eurostat does in exceptional periods.")
    product = st.selectbox("Product", products, key="season_product",
                           format_func=lambda p: product_label(p, hs2))

    # ---- typical year ----
    SF, fit = season(product, flow, measure, freeze)
    pr = profile(SF, y0, ya, yb)
    st.markdown(f"#### Typical year · {product_label(product, hs2)}")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Strongest month", MONTHS_LONG[pr["peak"]], f"{(pr['mean'][pr['peak']] - 1) * 100:+.1f}% vs trend")
    m2.metric("Weakest month", MONTHS_LONG[pr["low"]], f"{(pr['mean'][pr['low']] - 1) * 100:+.1f}% vs trend")
    m3.metric("Seasonal swing", f"{pr['swing'] * 100:.0f} pts", "strongest minus weakest", delta_color="off")
    m4.metric("One extra working day",
              f"{(np.exp(fit['wd']) - 1) * 100:+.1f}%" if fit["use_wd"] else "No significant effect",
              f"t = {fit['t_wd']:.1f}", delta_color="off")
    st.plotly_chart(typical_year_figure(pr, ya, yb), key="season_chart")
    st.caption(f"Bars: average seasonal factor per month, {ya}–{yb}, after calendar adjustment. "
               "Whiskers: lowest and highest factor in those years.")

    # ---- seasonality by product ----
    st.markdown("#### Seasonality by product")
    rows = product_table(flow, measure, ya, yb, freeze)
    st.session_state["season_codes"] = [r["code"] for r in rows]
    table = pd.DataFrame({
        "Product": [product_label(r["code"], hs2) for r in rows],
        "Jan → Dec": [r["profile"] for r in rows],
        "Swing (pts)": [r["swing"] for r in rows],
        "Peak": [r["peak"] for r in rows],
        "Low": [r["low"] for r in rows],
        "Per extra working day": ["n.s." if r["wd"] is None else f"{r['wd']:+.1f}%" for r in rows],
    })
    st.dataframe(
        table, hide_index=True, height=35 * (len(table) + 1) + 3, key="season_table", on_select=_pick_from_table, selection_mode="single-row",
        column_config={
            "Jan → Dec": st.column_config.LineChartColumn("Jan → Dec", help="Seasonal factor per month (own scale per row)"),
            "Swing (pts)": st.column_config.ProgressColumn("Swing (pts)", format="%.0f", min_value=0,
                                                           max_value=float(max(table["Swing (pts)"].max(), 1))),
            "Per extra working day": st.column_config.TextColumn(
                help="Effect of one extra working day in the month. n.s. = not statistically significant, so not applied."),
        })
    st.caption(f"All goods and the 20 largest {flow[:-1].lower()} chapters by value, {ya}–{yb}, ranked by seasonal swing. "
               "Select a row to show its typical year above. Very large swings in lumpy chapters (aircraft, pearls) "
               "mostly reflect one-off shipments rather than a true season.")
