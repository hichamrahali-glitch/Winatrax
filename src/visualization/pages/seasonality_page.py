"""Streamlit renderer for the seasonality view."""
from __future__ import annotations

def render(ctx):
    seasonality = ctx.seasonality
    seasonality.render()
