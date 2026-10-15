"""Streamlit renderer for the seasonality view."""
from __future__ import annotations

def render(ctx):
    st = ctx.st
    seasonality = ctx.seasonality
    st.header("When does Luxembourg trade?")
    seasonality.render()
