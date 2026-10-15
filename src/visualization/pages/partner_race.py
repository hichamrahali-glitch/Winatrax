"""Streamlit renderer for the partner race view."""
from __future__ import annotations

def render(ctx):
    st, pd = ctx.st, ctx.pd
    FRAMES = ctx.FRAMES
    flag, name, fmt = ctx.flag, ctx.name, ctx.fmt
    bar_race = ctx.bar_race
    measure, flow = ctx.measure, ctx.flow
    BY, COLOUR, UNIT = ctx.BY, ctx.COLOUR, ctx.UNIT
    blob, prod_label, idx = ctx.blob, ctx.prod_label, ctx.idx
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
