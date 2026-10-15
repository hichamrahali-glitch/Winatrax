"""Streamlit renderer for the world map view."""
from __future__ import annotations

def render(ctx):
    st = ctx.st
    D, product = ctx.D, ctx.product
    measure, flow = ctx.measure, ctx.flow
    prod_label, load_product = ctx.prod_label, ctx.load_product
    top5_map = ctx.top5_map
    st.caption("Luxembourg's five largest partners at each point in time, with the map zooming to them. "
               "Press ▶ to play, drag the timeline, or switch flow and measure on the map. "
               "The product follows the sidebar.")
    map_blobs = {m: (D["measures"][m]["total"] if product == "TOTAL" else load_product(product)[m])
                 for m in ("value", "quantity")}
    top5_map.render(D, map_blobs, "all goods" if product == "TOTAL" else prod_label, measure, flow)
