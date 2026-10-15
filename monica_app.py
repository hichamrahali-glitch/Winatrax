"""Luxembourg's trade in goods - interactive explorer (Streamlit + Plotly).

Run from the project root:
    .venv/bin/streamlit run app.py

Data: the JSON files written by python/04_build_race_page.py and
python/08_build_transport_page.py (output/app_data.json, output/products/*.json,
output/partners/*.json, output/transport_data.json). Partner countries without a
prepared file are fetched live from the Eurostat API (python/trade_tree.py).
"""
import json
import sys
from pathlib import Path
import seasonality
import top5_map

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "python"))
from trade_tree import fetch_partner_live  # noqa: E402

OUT = ROOT / "output"
EXPORT_COL, IMPORT_COL, GREY = "#2a78d6", "#eb6834", "#c3c2b7"
PALETTE = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
COUNTRY_COLOURS = dict(zip(["DE", "FR", "BE", "NL", "IT", "GB", "US", "ES"], PALETTE))
MODE_NAMES = {"road": "Road", "rail": "Rail", "inland_waterway": "Inland waterway", "sea": "Sea", "air": "Air",
              "other": "Other / not included"}
MODE_ICONS = {"road": "🚚", "rail": "🚆", "inland_waterway": "🛳️", "sea": "🚢", "air": "✈️", "other": "📦"}
MODE_COLOURS = {"road": "#eb6834", "rail": "#1baf7a", "inland_waterway": "#eda100", "sea": "#2a78d6",
                "air": "#e87ba4", "other": GREY}

st.set_page_config(page_title="Luxembourg trade explorer", page_icon="🇱🇺", layout="wide")


# ---- data -------------------------------------------------------------------
@st.cache_data
def load_app_data():
    return json.loads((OUT / "app_data.json").read_text(encoding="utf-8"))


@st.cache_data
def load_product(code):
    return json.loads((OUT / "products" / f"{code}.json").read_text(encoding="utf-8"))


@st.cache_data(show_spinner=False)
def load_partner(code, year):
    f = OUT / "partners" / f"{code}.json"
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8")), "prepared"
    return fetch_partner_live(code, year), "live"


@st.cache_data
def load_transport():
    return json.loads((OUT / "transport_data.json").read_text(encoding="utf-8"))


D = load_app_data()
FRAMES = D["frames"]                                        # "YYYY-MM", each = 12 months up to that month
DATES = pd.to_datetime([f + "-01" for f in FRAMES])
NAMES, HS2 = D["names"], D["hs2"]


def flag(code):
    """Emoji flag from a 2-letter code (renders as letters on some Windows browsers)."""
    code = {"EL": "GR", "UK": "GB", "XS": "RS"}.get(code, code)
    if len(code) != 2 or not code.isalpha():
        return ""
    return "".join(chr(0x1F1E6 + ord(ch) - 65) for ch in code.upper())


def name(code):
    return NAMES.get(code, code)


def fmt(v, measure):
    """Stored units: quantity in thousand tonnes, value in million EUR."""
    if v is None:
        return "–"
    if measure == "value":
        if v >= 1000:
            return f"€{v / 1000:.1f} bn"
        if v >= 1:
            return f"€{v:.0f} m" if v >= 100 else f"€{v:.1f} m"
        return f"€{v * 1000:.0f} k"
    if v >= 1000:
        return f"{v / 1000:.1f} Mt"
    if v >= 10:
        return f"{v:.0f} kt"
    if v >= 0.01:
        return f"{v:.2f} kt"
    return f"{v * 1000:.0f} t"


def period(i):
    y, m = FRAMES[i].split("-")
    return f"12 months to {pd.Timestamp(int(y), int(m), 1):%b %Y}"


def frame_indices(step):
    n = len(FRAMES)
    if step == "Monthly":
        idx = list(range(n))
    elif step == "Quarterly":
        idx = [i for i, f in enumerate(FRAMES) if f[5:] in ("03", "06", "09", "12")]
    else:
        idx = [i for i, f in enumerate(FRAMES) if f[5:] == "12"]
    return idx if idx[-1] == n - 1 else idx + [n - 1]


def play_controls(labels, duration, start_index):
    """Play / pause buttons and a period slider for an animated Plotly figure."""
    return dict(
        updatemenus=[dict(type="buttons", direction="left", x=0, y=1.13, xanchor="left", yanchor="top",
                          pad=dict(r=8, t=0), showactive=False, buttons=[
                              dict(label="▶ Play", method="animate",
                                   args=[None, dict(frame=dict(duration=duration, redraw=True),
                                                    transition=dict(duration=int(duration * 0.8), easing="linear"),
                                                    fromcurrent=False, mode="immediate")]),
                              dict(label="❚❚ Pause", method="animate",
                                   args=[[None], dict(frame=dict(duration=0, redraw=False),
                                                      transition=dict(duration=0), mode="immediate")])])],
        sliders=[dict(active=start_index, x=0.12, len=0.88, y=1.13, yanchor="top", pad=dict(t=0, b=10),
                      currentvalue=dict(visible=False), steps=[
                          dict(label=lab, method="animate",
                               args=[[lab], dict(frame=dict(duration=0, redraw=True), mode="immediate",
                                                 transition=dict(duration=200))]) for lab in labels])])


def big_period_label(text):
    return [dict(text=text, xref="paper", yref="paper", x=0.99, y=0.04, xanchor="right", yanchor="bottom",
                 showarrow=False, font=dict(size=46, color="rgba(120,120,120,0.25)"))]


# ---- generic animated charts ------------------------------------------------
def bar_race(items_at, indices, colour, n, value_title):
    """items_at(i) -> list of dicts {id, value, text, hover}, sorted descending."""
    frames, labels = [], []
    for i in indices:
        # n visible bars + up to 5 below the chart, so countries leaving the top n slide out
        # downwards instead of jumping (their labels are blank and clipped by the axis range)
        items = items_at(i)[:n + 5]
        for k, d in enumerate(items):
            if k >= n:
                d["text"] = ""
        lab = FRAMES[i]
        labels.append(lab)
        # Each frame is scaled so the leader fills the width (Plotly does not animate axis
        # ranges reliably); the real values are in the labels and the hover text.
        vmax = max([d["value"] for d in items[:n]] + [1e-9])
        frames.append(go.Frame(name=lab, data=[go.Bar(
            x=[d["value"] / vmax for d in items], y=list(range(1, len(items) + 1)), ids=[d["id"] for d in items],
            orientation="h", marker_color=colour, text=[d["text"] for d in items], textposition="outside",
            cliponaxis=True, hovertext=[d["hover"] for d in items], hoverinfo="text")],
            layout=go.Layout(annotations=big_period_label(period(i)))))
    last = frames[-1]
    fig = go.Figure(data=last.data, frames=frames)
    fig.update_layout(height=max(420, 30 * n + 140), margin=dict(l=10, r=10, t=90, b=30),
                      xaxis=dict(range=[0, 1.75], showticklabels=False, showgrid=False, title=None),
                      yaxis=dict(range=[n + 0.5, 0.5], tickvals=list(range(1, n + 1)), title=None),
                      annotations=last.layout.annotations, showlegend=False,
                      **play_controls(labels, 140, len(labels) - 1))
    return fig


def line_race(codes, series, indices, label, colour_of, highlight, value_title, measure):
    """Lines grow over time; top 5 (+ highlighted) in colour with a label at the line tip."""
    labels, frames = [], []
    top = set(codes[:5]) | set(highlight)
    order = [c for c in codes if c not in top] + [c for c in codes if c in top]
    for i in indices:
        data = []
        for c in order:
            col = colour_of(c) if c in codes[:5] else ("#0b0b0b" if c in highlight else GREY)
            data.append(go.Scatter(x=DATES[:i + 1], y=series[c][:i + 1], mode="lines", name=label(c),
                                   line=dict(color=col, width=2.4 if c in top else 1),
                                   hovertemplate=f"{label(c)}<br>%{{x|%b %Y}}: %{{y:,.2f}}<extra></extra>"))
        tips = [c for c in codes if c in top]
        data.append(go.Scatter(x=[DATES[i]] * len(tips), y=[series[c][i] for c in tips], mode="markers+text",
                               text=[f"{label(c)}  {fmt(series[c][i], measure)}" for c in tips],
                               textposition="middle right", cliponaxis=False, hoverinfo="skip",
                               marker=dict(size=7, color=[colour_of(c) if c in codes[:5] else "#0b0b0b" for c in tips])))
        lab = FRAMES[i]
        labels.append(lab)
        frames.append(go.Frame(name=lab, data=data, layout=go.Layout(annotations=big_period_label(lab[:4]))))
    last = frames[-1]
    fig = go.Figure(data=last.data, frames=frames)
    fig.update_layout(height=560, margin=dict(l=10, r=230, t=90, b=30), showlegend=False,
                      xaxis=dict(range=[DATES[0], DATES[-1]]),
                      yaxis=dict(range=[0, max([max(series[c]) for c in codes] + [1e-9]) * 1.08], title=value_title),
                      annotations=last.layout.annotations, **play_controls(labels, 90, len(labels) - 1))
    return fig


# ---- sidebar ----------------------------------------------------------------
st.sidebar.title("🇱🇺 Luxembourg trade")
measure = st.sidebar.radio("Measure", ["quantity", "value"],
                           format_func=lambda m: "Quantity (tonnes)" if m == "quantity" else "Value (€)")
flow = st.sidebar.radio("Flow", ["Exports", "Imports"])
step = st.sidebar.select_slider("Animation detail", ["Yearly", "Quarterly", "Monthly"], value="Quarterly",
                                help="More frames = smoother animation, but slower to load.")
product_codes = [p["code"] for p in D["products"]]
product_names = {p["code"]: p["name"] for p in D["products"]}
product = st.sidebar.selectbox("Product category (partner tabs)", product_codes,
                               format_func=lambda c: "All goods" if c == "TOTAL" else f"{c} – {HS2.get(c, {}).get('name', product_names[c])}")
st.sidebar.caption("Source: Eurostat (Comext DS-045409 and others). Each value is the total over the previous "
                   "12 months. Quantity in tonnes (Eurostat reports units of 100 kg); value in euros.")

UNIT = "thousand tonnes" if measure == "quantity" else "million €"
BY = "by weight" if measure == "quantity" else "by value"
COLOUR = EXPORT_COL if flow == "Exports" else IMPORT_COL
blob = (D["measures"][measure]["total"] if product == "TOTAL" else load_product(product)[measure])[flow]
prod_label = "goods" if product == "TOTAL" else HS2.get(product, {}).get("name", product_names[product]).lower()
idx = frame_indices(step)

st.title("Luxembourg's trade in goods")
tabs = st.tabs(["Partners race", "Partners lines", "Products race", "Products lines",
                "Partner detail", "Country comparison", "Transport & CO₂", "Seasonality", "World map"])

# ---- 1. Partners race -------------------------------------------------------
with tabs[0]:
    st.subheader(f"Who are Luxembourg's main trading partners for {prod_label}?")
    st.caption(f"Top 20 {'destinations' if flow == 'Exports' else 'origins'} {BY}, {FRAMES[0][:4]}–{FRAMES[-1][:4]}. "
               "Press ▶ Play to watch the ranking change, or drag the slider.")

    def partner_items(i):
        return [{"id": p, "value": v, "text": f"{flag(p)} {name(p)}  {fmt(v, measure)}",
                 "hover": f"#{r + 1} {name(p)}: {fmt(v, measure)}"} for r, (p, v, prev) in enumerate(blob["frames"][i])]

    if any(blob["frames"]):
        st.plotly_chart(bar_race(partner_items, idx, COLOUR, 20, UNIT))
        sel = st.select_slider("Table for the period ending", options=list(range(len(FRAMES))), value=len(FRAMES) - 1,
                               format_func=lambda i: FRAMES[i], key="race_period")
        world = blob["world"][sel]
        rows = []
        for r, (p, v, prev) in enumerate(blob["frames"][sel][:20]):
            rank = r + 1
            change = "New" if not prev else ("=" if prev == rank else (f"▲ {prev - rank}" if prev > rank else f"▼ {rank - prev}"))
            rows.append({"Rank": rank, "Change vs. a year earlier": change, "Country": f"{flag(p)} {name(p)}",
                         "Amount": fmt(v, measure), "Share of total": f"{v / world:.1%}" if world else "–"})
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    else:
        st.info("No trade recorded for this product.")

# ---- 2. Partners lines ------------------------------------------------------
with tabs[1]:
    st.subheader(f"Top 20 {'destinations' if flow == 'Exports' else 'origins'} over time ({prod_label})")
    codes = blob["top20"]
    if codes:
        hl = st.multiselect("Highlight countries", codes, format_func=lambda c: f"{flag(c)} {name(c)}", key="hl_partners")
        colours = {c: COUNTRY_COLOURS.get(c, PALETTE[k % len(PALETTE)]) for k, c in enumerate(codes[:5])}
        st.plotly_chart(line_race(codes, blob["series"], frame_indices("Yearly" if step == "Yearly" else "Quarterly"),
                                  lambda c: f"{flag(c)} {name(c)}", lambda c: colours.get(c, GREY), hl, UNIT, measure))
        st.caption("The 20 countries are the biggest in the latest 12 months; the top 5 are in colour. "
                   "▶ Play replays the lines from 1999.")
    else:
        st.info("No trade recorded for this product in the latest 12 months.")

# ---- 3. Products race -------------------------------------------------------
PR = D["measures"][measure]["prodrace"][flow]
with tabs[2]:
    st.subheader("What does Luxembourg export?" if flow == "Exports" else "What does Luxembourg import?")
    st.caption(f"Main product groups (2-digit codes) {BY}. The flag shows the country where most of each product "
               f"{'goes to' if flow == 'Exports' else 'comes from'}, with its share.")

    def product_items(i):
        out = []
        for r, (c, v, prev, lead, share) in enumerate(PR["frames"][i]):
            h = HS2.get(c, {"name": c, "icon": "📦"})
            partner = f"  ·  {flag(lead)} {name(lead)} {share:.0%}" if lead else ""
            out.append({"id": c, "value": v, "text": f"{h['icon']} {h['name']}  {fmt(v, measure)}{partner}",
                        "hover": f"#{r + 1} {h['name']}: {fmt(v, measure)}"})
        return out

    st.plotly_chart(bar_race(product_items, idx, COLOUR, 15, UNIT))
    sel = st.select_slider("Table for the period ending", options=list(range(len(FRAMES))), value=len(FRAMES) - 1,
                           format_func=lambda i: FRAMES[i], key="prod_period")
    total = PR["total"][sel]
    rows = []
    for r, (c, v, prev, lead, share) in enumerate(PR["frames"][sel][:20]):
        rank = r + 1
        change = "New" if not prev else ("=" if prev == rank else (f"▲ {prev - rank}" if prev > rank else f"▼ {rank - prev}"))
        h = HS2.get(c, {"name": c, "icon": "📦"})
        rows.append({"Rank": rank, "Change": change, "Product group": f"{h['icon']} {c} {h['name']}",
                     "Amount": fmt(v, measure), "Share of total": f"{v / total:.1%}" if total else "–",
                     "Main partner": f"{flag(lead)} {name(lead)} ({share:.0%})" if lead else "–"})
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

# ---- 4. Products lines ------------------------------------------------------
with tabs[3]:
    st.subheader("Main product groups over time")
    pcodes = PR["top"]
    hlp = st.multiselect("Highlight product groups", pcodes, format_func=lambda c: f"{HS2.get(c, {}).get('icon', '')} {HS2.get(c, {}).get('name', c)}",
                         key="hl_products")
    pcol = {c: PALETTE[k] for k, c in enumerate(pcodes[:5])}
    st.plotly_chart(line_race(pcodes, PR["series"], frame_indices("Yearly" if step == "Yearly" else "Quarterly"),
                              lambda c: f"{HS2.get(c, {}).get('icon', '')} {HS2.get(c, {}).get('name', c)}",
                              lambda c: pcol.get(c, GREY), hlp, UNIT, measure))
    st.caption(f"The {len(pcodes)} biggest product groups in the latest 12 months; the top 5 are in colour.")

# ---- 5. Partner detail ------------------------------------------------------
with tabs[4]:
    PD = D["partnerDetail"]
    year = PD["year"]
    prepared = [p["code"] for p in PD["list"]]
    live = [p["code"] for p in PD.get("live", [])]
    st.subheader("For a given partner country, what are the main goods traded with Luxembourg?")
    c1, c2 = st.columns([2, 1])
    partner = c1.selectbox("Partner country", prepared + live, key="partner",
                           format_func=lambda c: f"{flag(c)} {name(c)}" + ("" if c in prepared else "  (loaded live from Eurostat)"))
    share = c2.slider("Show items making up this share of trade", 50, 95, 80, 5, format="%d%%",
                      help="At every level, smaller items are grouped as “Other”.") / 100
    try:
        with st.spinner("Loading from Eurostat…" if partner in live else "Loading…"):
            pdata, source = load_partner(partner, year)
    except Exception as e:                                   # e.g. no internet for a live partner
        st.error(f"Could not load {name(partner)}: {e}")
        pdata = None
    if pdata:
        root = pdata[measure][flow]
        labels = pdata["labels"]
        exp = flow == "Exports"
        st.markdown(f"**{'Exports to' if exp else 'Imports from'} {flag(partner)} {name(partner)}, {year}: "
                    f"{fmt(root['v'], measure)}**" + ("  ·  _loaded live from the Eurostat API_" if source == "live" else ""))

        def node_label(code):
            if len(code) == 2:
                h = HS2.get(code, {"name": code, "icon": ""})
                return f"{h['icon']} {code} {h['name']}"
            text = labels.get(code, code)
            return f"{code} {text[:60] + '…' if len(text) > 60 else text}"

        ids, parents, texts, vals, hovers = [], [], [], [], []

        def walk(node, node_id, parent_id):
            """Add a node and its shown children; returns the value used for the node.
            Plotly treemaps draw nothing if a parent is smaller than the sum of its children,
            so a parent's value is computed from what is shown inside it (bottom-up)."""
            pos = len(ids)
            ids.append(node_id)
            parents.append(parent_id)
            vals.append(0)
            texts.append("All goods" if node["c"] == "TOTAL" else node_label(node["c"]))
            full = "All goods" if node["c"] == "TOTAL" else (HS2.get(node["c"], {}).get("full") if len(node["c"]) == 2 else labels.get(node["c"], node["c"]))
            hovers.append(f"{full}<br>{fmt(node['v'], measure)}")
            kids, shown, cum = node.get("k", []), [], 0.0
            for k in kids:
                if shown and cum >= share * node["v"]:
                    break
                shown.append(k)
                cum += k["v"]
            inside = sum(walk(k, f"{node_id}/{k['c']}", node_id) for k in shown)
            other_n = len(kids) - len(shown) + node.get("n", 0)
            other_v = round(node["v"] - cum, 6)
            if kids and other_v > 0 and other_n > 0:
                ids.append(f"{node_id}/other")
                parents.append(node_id)
                vals.append(other_v)
                texts.append(f"Other ({other_n} smaller items)")
                hovers.append(f"{other_n} smaller items grouped<br>{fmt(other_v, measure)}")
                inside += other_v
            vals[pos] = max(node["v"], inside * (1 + 1e-9))   # tiny margin for float sums
            return vals[pos]

        walk(root, "TOTAL", "")
        fig = go.Figure(go.Treemap(ids=ids, parents=parents, values=vals, labels=texts, branchvalues="total",
                                   maxdepth=2, hovertext=hovers, hoverinfo="text",
                                   texttemplate="%{label}<br>%{percentParent:.0%}",
                                   marker=dict(colors=[GREY if t.startswith("Other") else COLOUR for t in texts],
                                               line=dict(width=1, color="white")), pathbar=dict(visible=True)))
        fig.update_layout(height=620, margin=dict(l=0, r=0, t=30, b=0))
        st.plotly_chart(fig)
        st.caption("Click a box to go one level deeper: 2-digit chapters → 4-digit headings → 6-digit subheadings → "
                   "8-digit products (CN8). Click the bar at the top to go back up. Percentages are shares of the level above.")

        leaves = []

        def collect(node):
            if len(node["c"]) == 8:
                leaves.append(node)
            for k in node.get("k", []):
                collect(k)
        collect(root)
        if leaves:
            leaves.sort(key=lambda n: -n["v"])
            st.markdown("**Most significant 8-digit products**")
            st.dataframe(pd.DataFrame([{"CN8 code": n["c"], "Product": labels.get(n["c"], n["c"]),
                                        "Amount": fmt(n["v"], measure), "Share of total": f"{n['v'] / root['v']:.1%}"}
                                       for n in leaves[:15]]), hide_index=True, width="stretch")

# ---- 6. Country comparison --------------------------------------------------
with tabs[5]:
    CMP = D["countries"]
    st.subheader("How does Luxembourg's trade compare with other EU countries?")
    scale = st.radio("Scale", ["total", "pc"], horizontal=True, key="cmp_scale",
                     format_func=lambda s: "Total" if s == "total" else "Per inhabitant")
    years = CMP["years"]

    def per_cap(v, pop):
        if v is None or not pop:
            return None
        return v * 1e6 / pop if measure == "value" else v * 1000 / pop     # € or tonnes per person

    def cfmt(x):
        if x is None:
            return "–"
        if scale == "pc":
            return f"€{x:,.0f}" if measure == "value" else f"{x:.1f} t"
        return fmt(x, measure)

    def values_for(i):
        out = []
        for code, s in CMP["series"].items():
            ex, im, pop = s[measure]["Exports"][i], s[measure]["Imports"][i], s["pop"][i]
            if scale == "pc":
                ex, im = per_cap(ex, pop), per_cap(im, pop)
            if ex is not None and im is not None:
                out.append((code, ex, im))
        out.sort(key=lambda d: -(d[1] + d[2]))
        rank = {d[0]: r + 1 for r, d in enumerate(out)}
        lu = [d for d in out if d[0] == "LU"]
        return lu + [d for d in out if d[0] != "LU"], rank          # Luxembourg pinned to the top

    def eu_avg(i):
        ex = im = pop = 0
        for c in CMP["eu27"]:
            s = CMP["series"].get(c)
            if s and s[measure]["Exports"][i] is not None and s["pop"][i]:
                ex += s[measure]["Exports"][i]
                im += s[measure]["Imports"][i]
                pop += s["pop"][i]
        return (per_cap(ex, pop), per_cap(im, pop)) if pop else (None, None)

    frames, labels_y = [], []
    gmax = 0
    for i, y in enumerate(years):
        rows, rank = values_for(i)
        gmax = max([gmax] + [max(d[1], d[2]) for d in rows])
    for i, y in enumerate(years):
        rows, rank = values_for(i)
        pos = list(range(len(rows)))
        ticks = [f"{rank[c]}. {flag(c)} {name(c)}" for c, _, _ in rows]
        shapes = []
        if scale == "pc":
            ea, ia = eu_avg(i)
            if ea:
                shapes = [dict(type="line", x0=-ea, x1=-ea, y0=-0.5, y1=len(rows) - 0.5, line=dict(dash="dash", color="#52514e")),
                          dict(type="line", x0=ia, x1=ia, y0=-0.5, y1=len(rows) - 0.5, line=dict(dash="dash", color="#52514e"))]
        op = [1 if c == "LU" else 0.45 for c, _, _ in rows]
        frames.append(go.Frame(name=y, data=[
            go.Bar(x=[-d[1] for d in rows], y=pos, ids=[f"E{d[0]}" for d in rows], orientation="h", name="Exports",
                   marker=dict(color=EXPORT_COL, opacity=op), text=[cfmt(d[1]) for d in rows], textposition="outside",
                   cliponaxis=False, hovertext=[f"{name(d[0])} exports: {cfmt(d[1])}" for d in rows], hoverinfo="text"),
            go.Bar(x=[d[2] for d in rows], y=pos, ids=[f"I{d[0]}" for d in rows], orientation="h", name="Imports",
                   marker=dict(color=IMPORT_COL, opacity=op), text=[cfmt(d[2]) for d in rows], textposition="outside",
                   cliponaxis=False, hovertext=[f"{name(d[0])} imports: {cfmt(d[2])}" for d in rows], hoverinfo="text")],
            layout=go.Layout(yaxis=dict(tickvals=pos, ticktext=ticks), shapes=shapes,
                             annotations=big_period_label(str(y)))))
    last = frames[-1]
    tick_vals = [v * gmax for v in (-1, -0.5, 0, 0.5, 1)]
    fig = go.Figure(data=last.data, frames=frames)
    fig.update_layout(barmode="overlay", bargap=0.25, height=860, margin=dict(l=10, r=10, t=90, b=40),
                      xaxis=dict(range=[-gmax * 1.3, gmax * 1.3], tickvals=tick_vals,
                                 ticktext=[cfmt(abs(v)) for v in tick_vals], title="◀ Exports    |    Imports ▶"),
                      yaxis=dict(autorange="reversed", tickvals=last.layout.yaxis.tickvals,
                                 ticktext=last.layout.yaxis.ticktext),
                      shapes=last.layout.shapes, annotations=last.layout.annotations,
                      legend=dict(orientation="h", y=-0.06), **play_controls([str(y) for y in years], 700, len(years) - 1))
    st.plotly_chart(fig)
    st.caption("Luxembourg is pinned to the top row; the number before each name is the country's rank by total trade. "
               "“Per inhabitant” divides by population (dashed lines = EU average). Goods only, not services.")
    ysel = st.select_slider("Table for year", options=years, value=years[-1], key="cmp_year")
    rows, rank = values_for(years.index(ysel))
    st.dataframe(pd.DataFrame([{"Rank": rank[c], "Country": f"{flag(c)} {name(c)}", "Exports": cfmt(ex), "Imports": cfmt(im),
                                "Balance": ("+" if ex >= im else "−") + cfmt(abs(ex - im)), "Total": cfmt(ex + im)}
                               for c, ex, im in rows]), hide_index=True, width="stretch")

# ---- 7. Transport & CO2 -----------------------------------------------------
with tabs[6]:
    T = load_transport()
    st.subheader("How do Luxembourg's goods travel, and what does it cost the climate?")
    st.warning("The CO₂ figures are an **estimate** (tonnes × distance × GLEC emission factor). Customs record the "
               "transport mode only for trade with non-EU countries; for EU countries it is assumed from "
               "Luxembourg's national freight split. See the method below.")
    tflow = st.radio("Trade flow", ["Both", "Exports", "Imports"], horizontal=True, key="t_flow",
                     format_func=lambda f: "Exports + imports" if f == "Both" else f)
    S = T["summary"][tflow]
    modes = T["modes"]
    t_all, c_all = sum(S["all"]["tonnes"].values()), sum(S["all"]["co2"].values())

    def tf(t):
        return f"{t / 1e6:.1f} Mt" if t >= 1e6 else (f"{t / 1e3:,.0f} kt" if t >= 1e3 else f"{t:,.0f} t")

    k1, k2, k3 = st.columns(3)
    k1.metric(f"Estimated transport CO₂, {T['year']}", tf(c_all) + " CO₂e",
              help=f"{sum(S['eu']['co2'].values()) / c_all:.0%} from trade with EU countries")
    k2.metric("Air freight", f"{S['all']['co2']['air'] / c_all:.0%} of the CO₂",
              f"only {S['all']['tonnes']['air'] / t_all:.1%} of the tonnes", delta_color="off")
    k3.metric("Road freight", f"{S['all']['co2']['road'] / c_all:.0%} of the CO₂",
              f"{S['all']['tonnes']['road'] / t_all:.0%} of the tonnes", delta_color="off")

    scope = st.radio("Coverage", ["all", "extra"], horizontal=True, key="t_scope",
                     format_func=lambda s: "All trade" if s == "all" else "Non-EU trade only (mode measured)")
    part = S[scope]
    fig = go.Figure()
    for m in modes:
        tt, cc = sum(part["tonnes"].values()), sum(part["co2"].values())
        fig.add_bar(y=["Share of CO₂", "Share of tonnes"], x=[part["co2"][m] / cc * 100, part["tonnes"][m] / tt * 100],
                    orientation="h", name=f"{MODE_ICONS[m]} {MODE_NAMES[m]}", marker_color=MODE_COLOURS[m],
                    hovertemplate="%{x:.1f}%<extra>" + MODE_NAMES[m] + "</extra>")
    fig.update_layout(barmode="stack", height=230, margin=dict(l=10, r=10, t=10, b=10), xaxis=dict(range=[0, 100], ticksuffix="%"),
                      legend=dict(orientation="h", y=-0.25))
    st.plotly_chart(fig)
    factors = {f["mode"]: f["factor"] for f in T["factors"]}
    st.dataframe(pd.DataFrame([{
        "Mode": f"{MODE_ICONS[m]} {MODE_NAMES[m]}", "Goods (tonnes)": f"{part['tonnes'][m]:,.0f}",
        "CO₂ (t CO₂e)": "not estimated" if m == "other" else f"{part['co2'][m]:,.0f}",
        "kg CO₂ per tonne": "–" if m == "other" or not part["tonnes"][m] else f"{part['co2'][m] * 1000 / part['tonnes'][m]:,.0f}",
        "GLEC factor (g/t-km)": "788–1,363" if m == "air" else str(factors.get(m, "–"))}
        for m in modes if part["tonnes"][m] > 0]), hide_index=True, width="stretch")

    st.markdown("#### How do goods to and from non-EU countries travel? (measured)")
    tm = st.radio("Measure", ["value", "tonnes"], horizontal=True, key="t_trend",
                  format_func=lambda m: "By value (€)" if m == "value" else "By weight (tonnes)")
    flows = ["Exports", "Imports"] if tflow == "Both" else [tflow]
    fig = go.Figure()
    for m in modes:
        y = [sum(T["trend"][f][tm][m][i] for f in flows) for i in range(len(T["years"]))]
        fig.add_bar(x=T["years"], y=y, name=f"{MODE_ICONS[m]} {MODE_NAMES[m]}", marker_color=MODE_COLOURS[m])
    fig.update_layout(barmode="stack", height=380, margin=dict(l=10, r=10, t=10, b=10),
                      yaxis_title="million €" if tm == "value" else "tonnes", legend=dict(orientation="h", y=-0.15))
    st.plotly_chart(fig)

    def stacked_top(items, label):
        fig = go.Figure()
        ys = [label(d) for d in items]
        for m in ["road", "rail", "inland_waterway", "sea", "air"]:
            fig.add_bar(y=ys, x=[d["byMode"][m] / 1000 for d in items], orientation="h", name=f"{MODE_ICONS[m]} {MODE_NAMES[m]}",
                        marker_color=MODE_COLOURS[m], hovertemplate="%{x:,.1f} kt CO₂e<extra>" + MODE_NAMES[m] + "</extra>")
        fig.update_layout(barmode="stack", height=40 + 28 * len(items), margin=dict(l=10, r=10, t=10, b=10),
                          yaxis=dict(autorange="reversed"), xaxis_title="thousand tonnes CO₂e (estimated)",
                          legend=dict(orientation="h", y=-0.12))
        return fig

    st.markdown("#### Which partner countries cause the most transport CO₂? (estimate)")
    st.plotly_chart(stacked_top(S["partners"], lambda d: f"{flag(d['code'])} {d['name']} {'(EU, mode estimated)' if d['eu'] else '(non-EU)'}"))
    st.markdown("#### Which products (non-EU trade) cause the most transport CO₂? (estimate)")
    st.plotly_chart(stacked_top(S["products"], lambda d: f"{d['icon']} {d['name']}"))

    st.markdown("#### Context: Luxembourg, an air cargo hub (measured)")
    c = T["context"]
    a1, a2 = st.columns(2)
    a1.metric(f"Air freight through Luxembourg airport, {c['airport']['year']}", tf(c["airport"]["tonnes"]),
              f"Luxembourg's own non-EU trade by air: {tf(c['own_air_tonnes'])} ({c['own_air_tonnes'] / c['airport']['tonnes']:.0%})",
              delta_color="off")
    k = c["co2_accounts"]
    a2.metric(f"CO₂ of all industries in Luxembourg, {k['year']}", f"{k['air_transport'] / k['total']:.0%} from air transport",
              f"{tf(k['air_transport'])} of {tf(k['total'])} (covers flights worldwide)", delta_color="off")

    with st.expander("How these numbers are calculated", expanded=False):
        sp, A = T["split"]["shares"], T["assumptions"]
        st.markdown(f"""
**Formula** (per partner country, flow and transport mode):
`CO₂ (tonnes) = goods (tonnes) × distance (km) × emission factor (g CO₂e per tonne-km) ÷ 1,000,000`

- **Goods:** Eurostat DS-045409, total goods, {T['year']}.
- **Transport mode:** non-EU partners measured by customs (DS-059334); EU partners not recorded, so Luxembourg's inland freight
  modal split in {T['split']['year']} (tran_hv_frmod) is applied: road {sp['road']:.0%}, rail {sp['rail']:.0%}, inland waterway {sp['inland_waterway']:.0%}.
- **Distance:** straight line from Luxembourg City to the partner's centre; road/rail/waterway × {A['detour_land']}; air straight line
  (GLEC adds 95 km); sea = {A['road_to_antwerp_km']} km truck to Antwerp + sea route × {A['detour_sea']}.
- **Not included:** post, pipelines/power lines, self-propelled goods, unknown mode.
- **Limits:** order-of-magnitude estimate; real routes, vehicles and load factors vary; goods only.
""")
        st.dataframe(pd.DataFrame([{"Mode": f["mode"].replace("_", " "), "g CO₂e / t-km": f["factor"], "Source (GLEC Framework v3.1)": f["ref"]}
                                   for f in T["factors"]]), hide_index=True, width="stretch")

with tabs[7]:
    st.header("What does Luxembourg trade?")
    # KPI cards, timeline and product charts
    seasonality.render()
# ---- 9. World map -----------------------------------------------------------
with tabs[8]:
    st.caption("Luxembourg's five largest partners at each point in time, with the map zooming to them. "
               "Press ▶ to play, drag the timeline, or switch flow and measure on the map. "
               "The product follows the sidebar.")
    map_blobs = {m: (D["measures"][m]["total"] if product == "TOTAL" else load_product(product)[m])
                 for m in ("value", "quantity")}
    top5_map.render(D, map_blobs, "all goods" if product == "TOTAL" else prod_label, measure, flow)
