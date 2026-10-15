"""Story-led views of Luxembourg's changing trade portfolio.

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
from visualization.data import load_app_data, load_product
from visualization.formatting import (
    country_name, flag, format_value,
)
from visualization.world_map import adapter as top5_map

EXPORT_COL, IMPORT_COL = "#2a78d6", "#eb6834"

from visualization.pages import country_comparison, seasonality_page, world_map


def main():
    st.set_page_config(page_title="Luxembourg trade explorer", page_icon="🇱🇺", layout="wide")

    # ---- data -------------------------------------------------------------------
    D = load_app_data()
    NAMES, HS2 = D["names"], D["hs2"]

    name = lambda code: country_name(code, NAMES)
    fmt = format_value

    product_codes = [p["code"] for p in D["products"]]
    product_names = {p["code"]: p["name"] for p in D["products"]}
    st.title("How Luxembourg's trade portfolio changes")
    st.caption("Who it relies on, what it sells and buys, and how those patterns shift over time.")

    view_col, filters_col = st.columns([1.2, 4])
    view = view_col.selectbox("View", ["World map", "Country comparison", "Seasonality"])
    if view == "World map":
        measure_col, flow_col, product_col = filters_col.columns([1, 1, 2.4])
        measure = measure_col.selectbox(
            "Measure", ["quantity", "value"],
            format_func=lambda m: "Quantity (tonnes)" if m == "quantity" else "Value (€)",
        )
        flow = flow_col.selectbox("Flow", ["Exports", "Imports"])
        product = product_col.selectbox(
            "Product category", product_codes,
            format_func=lambda c: "All goods" if c == "TOTAL" else f"{c} – {HS2.get(c, {}).get('name', product_names[c])}",
        )
    elif view == "Country comparison":
        measure_col = filters_col.columns(1)[0]
        measure = measure_col.selectbox(
            "Measure", ["quantity", "value"],
            format_func=lambda m: "Quantity (tonnes)" if m == "quantity" else "Value (€)",
        )
        flow, product = "Exports", "TOTAL"
    else:
        measure, flow, product = "value", "Exports", "TOTAL"
    prod_label = "goods" if product == "TOTAL" else HS2.get(product, {}).get("name", product_names[product]).lower()
    st.caption("Source: Eurostat (Comext DS-045409 and others). Values cover the previous 12 months; "
               "quantities are in tonnes (Eurostat reports units of 100 kg).")

    ctx = SimpleNamespace(
        st=st, pd=pd, go=go, D=D, measure=measure, flow=flow,
        flag=flag, name=name, fmt=fmt,
        big_period_label=big_period_label, play_controls=play_controls,
        product=product, prod_label=prod_label, load_product=load_product,
        EXPORT_COL=EXPORT_COL, IMPORT_COL=IMPORT_COL,
        seasonality=seasonality, top5_map=top5_map,
    )
    if view == "World map":
        world_map.render(ctx)
    elif view == "Country comparison":
        country_comparison.render(ctx)
    else:
        seasonality_page.render(ctx)
