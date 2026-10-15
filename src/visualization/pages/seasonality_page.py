"""Streamlit renderer for the seasonality view."""
from __future__ import annotations

def render(ctx):
    st = ctx.st
    seasonality = ctx.seasonality
    st.header("What does Luxembourg trade?")
    # KPI cards, timeline and product charts
    seasonality.render()
