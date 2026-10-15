"""Streamlit renderer for the product trends view."""
from __future__ import annotations

def render(ctx):
    st = ctx.st
    D, HS2 = ctx.D, ctx.HS2
    frame_indices, line_race = ctx.frame_indices, ctx.line_race
    measure, flow, step = ctx.measure, ctx.flow, ctx.step
    UNIT, GREY, PALETTE = ctx.UNIT, ctx.GREY, ctx.PALETTE
    PR = D["measures"][measure]["prodrace"][flow]
    st.subheader("Main product groups over time")
    pcodes = PR["top"]
    hlp = st.multiselect("Highlight product groups", pcodes, format_func=lambda c: f"{HS2.get(c, {}).get('icon', '')} {HS2.get(c, {}).get('name', c)}",
                         key="hl_products")
    pcol = {c: PALETTE[k] for k, c in enumerate(pcodes[:5])}
    st.plotly_chart(line_race(pcodes, PR["series"], frame_indices("Yearly" if step == "Yearly" else "Quarterly"),
                              lambda c: f"{HS2.get(c, {}).get('icon', '')} {HS2.get(c, {}).get('name', c)}",
                              lambda c: pcol.get(c, GREY), hlp, UNIT, measure))
    st.caption(f"The {len(pcodes)} biggest product groups in the latest 12 months; the top 5 are in colour.")
