"""Streamlit renderer for the partner trends view."""
from __future__ import annotations

def render(ctx):
    st = ctx.st
    FRAMES = ctx.FRAMES
    flag, name = ctx.flag, ctx.name
    frame_indices, line_race = ctx.frame_indices, ctx.line_race
    measure, flow, step = ctx.measure, ctx.flow, ctx.step
    UNIT, blob, prod_label = ctx.UNIT, ctx.blob, ctx.prod_label
    GREY, PALETTE = ctx.GREY, ctx.PALETTE
    COUNTRY_COLOURS = ctx.COUNTRY_COLOURS
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
