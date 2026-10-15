"""Streamlit renderer for the world map view."""
from __future__ import annotations

def render(ctx):
    st = ctx.st
    D, top5_map = ctx.D, ctx.top5_map
    st.caption("Luxembourg's five largest partners at each point in time, with the map zooming to them. "
               "Press ▶ to play, drag the timeline, and use the flow and measure controls on the map.")
    map_blobs = {m: D["measures"][m]["total"] for m in ("value", "quantity")}
    top5_map.render(D, map_blobs, "all goods", "value", "Exports")
