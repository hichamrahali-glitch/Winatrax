"""Luxembourg's trade in goods - interactive explorer (Streamlit + Plotly).

Run from the project root:
    .venv/bin/streamlit run app.py

Reads prepared dashboard data from data/derived/. Partner countries without
prepared detail are fetched live from Eurostat.
"""
from types import SimpleNamespace

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from visualization import seasonality
from visualization.charts.animated import big_period_label, play_controls
from visualization.data import load_app_data, load_partner, load_product, load_transport
from visualization.formatting import (
    country_name, flag, format_value, frame_indices as select_frame_indices, period_label,
)
from visualization.world_map import adapter as top5_map

EXPORT_COL, IMPORT_COL, GREY = "#2a78d6", "#eb6834", "#c3c2b7"
PALETTE = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
COUNTRY_COLOURS = dict(zip(["DE", "FR", "BE", "NL", "IT", "GB", "US", "ES"], PALETTE))
MODE_NAMES = {"road": "Road", "rail": "Rail", "inland_waterway": "Inland waterway", "sea": "Sea", "air": "Air",
              "other": "Other / not included"}
MODE_ICONS = {"road": "🚚", "rail": "🚆", "inland_waterway": "🛳️", "sea": "🚢", "air": "✈️", "other": "📦"}
MODE_COLOURS = {"road": "#eb6834", "rail": "#1baf7a", "inland_waterway": "#eda100", "sea": "#2a78d6",
                "air": "#e87ba4", "other": GREY}

from visualization.pages import (
    country_comparison, partner_detail, partner_race, partner_trends,
    product_race, product_trends, seasonality_page, transport, world_map,
)


def main():
    st.set_page_config(page_title="Luxembourg trade explorer", page_icon="🇱🇺", layout="wide")

    # ---- data -------------------------------------------------------------------
    D = load_app_data()
    FRAMES = D["frames"]                                        # "YYYY-MM", each = 12 months up to that month
    DATES = pd.to_datetime([f + "-01" for f in FRAMES])
    NAMES, HS2 = D["names"], D["hs2"]


    name = lambda code: country_name(code, NAMES)
    fmt = format_value
    period = lambda i: period_label(i, FRAMES)
    frame_indices = lambda selected_step: select_frame_indices(selected_step, FRAMES)

    # ---- generic animated charts ------------------------------------------------
    from visualization.charts.animated import bar_race as build_bar_race
    from visualization.charts.animated import line_race as build_line_race

    def bar_race(items_at, indices, colour, n, value_title):
        return build_bar_race(
            items_at, indices, colour, n, value_title, frame_labels=FRAMES,
            period_label=period, controls=play_controls, big_label=big_period_label,
        )

    def line_race(codes, series, indices, label, colour_of, highlight, value_title, measure):
        return build_line_race(
            codes, series, indices, label, colour_of, highlight, value_title, measure,
            frame_labels=FRAMES, dates=DATES, formatter=fmt, controls=play_controls,
            big_label=big_period_label, grey=GREY,
        )

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

    ctx = SimpleNamespace(
        st=st, pd=pd, go=go, D=D, FRAMES=FRAMES, DATES=DATES, NAMES=NAMES, HS2=HS2,
        flag=flag, name=name, fmt=fmt, period=period, frame_indices=frame_indices,
        bar_race=bar_race, line_race=line_race, measure=measure, flow=flow, step=step,
        big_period_label=big_period_label, play_controls=play_controls,
        product=product, product_names=product_names, UNIT=UNIT, BY=BY, COLOUR=COLOUR,
        blob=blob, prod_label=prod_label, idx=idx, EXPORT_COL=EXPORT_COL,
        IMPORT_COL=IMPORT_COL, GREY=GREY, PALETTE=PALETTE,
        COUNTRY_COLOURS=COUNTRY_COLOURS, MODE_NAMES=MODE_NAMES,
        MODE_ICONS=MODE_ICONS, MODE_COLOURS=MODE_COLOURS,
        load_partner=load_partner, load_product=load_product, load_transport=load_transport,
        seasonality=seasonality, top5_map=top5_map,
    )
    with tabs[0]:
        partner_race.render(ctx)
    with tabs[1]:
        partner_trends.render(ctx)
    with tabs[2]:
        product_race.render(ctx)
    with tabs[3]:
        product_trends.render(ctx)
    with tabs[4]:
        partner_detail.render(ctx)
    with tabs[5]:
        country_comparison.render(ctx)
    with tabs[6]:
        transport.render(ctx)
    with tabs[7]:
        seasonality_page.render(ctx)
    with tabs[8]:
        world_map.render(ctx)
