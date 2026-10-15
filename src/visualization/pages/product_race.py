"""Streamlit renderer for the product race view."""
from __future__ import annotations

def render(ctx):
    st, pd = ctx.st, ctx.pd
    D, HS2 = ctx.D, ctx.HS2
    flag, name, fmt = ctx.flag, ctx.name, ctx.fmt
    bar_race = ctx.bar_race
    measure, flow = ctx.measure, ctx.flow
    BY, COLOUR, UNIT = ctx.BY, ctx.COLOUR, ctx.UNIT
    FRAMES, idx = ctx.FRAMES, ctx.idx
    PR = D["measures"][measure]["prodrace"][flow]
    st.subheader("What does Luxembourg export?" if flow == "Exports" else "What does Luxembourg import?")
    st.caption(f"Main product groups (2-digit codes) {BY}. The flag shows the country where most of each product "
               f"{'goes to' if flow == 'Exports' else 'comes from'}, with its share.")

    def product_items(i):
        out = []
        for r, (c, v, prev, lead, share) in enumerate(PR["frames"][i]):
            h = HS2.get(c, {"name": c, "icon": "📦"})
            partner = f"  ·  {flag(lead)} {name(lead)} {share:.0%}" if lead else ""
            out.append({"id": c, "value": v, "text": f"{h['icon']} {h['name']}  {fmt(v, measure)}{partner}",
                        "hover": f"#{r + 1} {h['name']}: {fmt(v, measure)}"})
        return out

    st.plotly_chart(bar_race(product_items, idx, COLOUR, 15, UNIT))
    sel = st.select_slider("Table for the period ending", options=list(range(len(FRAMES))), value=len(FRAMES) - 1,
                           format_func=lambda i: FRAMES[i], key="prod_period")
    total = PR["total"][sel]
    rows = []
    for r, (c, v, prev, lead, share) in enumerate(PR["frames"][sel][:20]):
        rank = r + 1
        change = "New" if not prev else ("=" if prev == rank else (f"▲ {prev - rank}" if prev > rank else f"▼ {rank - prev}"))
        h = HS2.get(c, {"name": c, "icon": "📦"})
        rows.append({"Rank": rank, "Change": change, "Product group": f"{h['icon']} {c} {h['name']}",
                     "Amount": fmt(v, measure), "Share of total": f"{v / total:.1%}" if total else "–",
                     "Main partner": f"{flag(lead)} {name(lead)} ({share:.0%})" if lead else "–"})
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
