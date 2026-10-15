"""Streamlit renderer for the country comparison view."""
from __future__ import annotations

def render(ctx):
    st, pd, go = ctx.st, ctx.pd, ctx.go
    D = ctx.D
    flag, name, fmt = ctx.flag, ctx.name, ctx.fmt
    EXPORT_COL, IMPORT_COL = ctx.EXPORT_COL, ctx.IMPORT_COL
    big_period_label, play_controls = ctx.big_period_label, ctx.play_controls
    CMP = D["countries"]
    measure = st.radio("Measure", ["quantity", "value"], horizontal=True, key="cmp_measure",
                       format_func=lambda m: "Quantity (tonnes)" if m == "quantity" else "Value (€)")
    scale = st.radio("Scale", ["total", "pc"], horizontal=True, key="cmp_scale",
                     format_func=lambda s: "Total" if s == "total" else "Per inhabitant")
    years = CMP["years"]

    def per_cap(v, pop):
        if v is None or not pop:
            return None
        return v * 1e6 / pop if measure == "value" else v * 1000 / pop     # € or tonnes per person

    def cfmt(x):
        if x is None:
            return "–"
        if scale == "pc":
            return f"€{x:,.0f}" if measure == "value" else f"{x:.1f} t"
        return fmt(x, measure)

    def values_for(i):
        out = []
        for code, s in CMP["series"].items():
            ex, im, pop = s[measure]["Exports"][i], s[measure]["Imports"][i], s["pop"][i]
            if scale == "pc":
                ex, im = per_cap(ex, pop), per_cap(im, pop)
            if ex is not None and im is not None:
                out.append((code, ex, im))
        out.sort(key=lambda d: -(d[1] + d[2]))
        rank = {d[0]: r + 1 for r, d in enumerate(out)}
        lu = [d for d in out if d[0] == "LU"]
        return lu + [d for d in out if d[0] != "LU"], rank          # Luxembourg pinned to the top

    def eu_avg(i):
        ex = im = pop = 0
        for c in CMP["eu27"]:
            s = CMP["series"].get(c)
            if s and s[measure]["Exports"][i] is not None and s["pop"][i]:
                ex += s[measure]["Exports"][i]
                im += s[measure]["Imports"][i]
                pop += s["pop"][i]
        return (per_cap(ex, pop), per_cap(im, pop)) if pop else (None, None)

    frames, labels_y = [], []
    gmax = 0
    for i, y in enumerate(years):
        rows, rank = values_for(i)
        gmax = max([gmax] + [max(d[1], d[2]) for d in rows])
    for i, y in enumerate(years):
        rows, rank = values_for(i)
        pos = list(range(len(rows)))
        ticks = [f"{rank[c]}. {flag(c)} {name(c)}" for c, _, _ in rows]
        shapes = []
        if scale == "pc":
            ea, ia = eu_avg(i)
            if ea:
                shapes = [dict(type="line", x0=-ea, x1=-ea, y0=-0.5, y1=len(rows) - 0.5, line=dict(dash="dash", color="#52514e")),
                          dict(type="line", x0=ia, x1=ia, y0=-0.5, y1=len(rows) - 0.5, line=dict(dash="dash", color="#52514e"))]
        op = [1 if c == "LU" else 0.45 for c, _, _ in rows]
        frames.append(go.Frame(name=y, data=[
            go.Bar(x=[-d[1] for d in rows], y=pos, ids=[f"E{d[0]}" for d in rows], orientation="h", name="Exports",
                   marker=dict(color=EXPORT_COL, opacity=op), text=[cfmt(d[1]) for d in rows], textposition="outside",
                   cliponaxis=False, hovertext=[f"{name(d[0])} exports: {cfmt(d[1])}" for d in rows], hoverinfo="text"),
            go.Bar(x=[d[2] for d in rows], y=pos, ids=[f"I{d[0]}" for d in rows], orientation="h", name="Imports",
                   marker=dict(color=IMPORT_COL, opacity=op), text=[cfmt(d[2]) for d in rows], textposition="outside",
                   cliponaxis=False, hovertext=[f"{name(d[0])} imports: {cfmt(d[2])}" for d in rows], hoverinfo="text")],
            layout=go.Layout(yaxis=dict(tickvals=pos, ticktext=ticks), shapes=shapes,
                             annotations=big_period_label(str(y)))))
    last = frames[-1]
    tick_vals = [v * gmax for v in (-1, -0.5, 0, 0.5, 1)]
    fig = go.Figure(data=last.data, frames=frames)
    fig.update_layout(barmode="overlay", bargap=0.25, height=860, margin=dict(l=10, r=10, t=90, b=40),
                      xaxis=dict(range=[-gmax * 1.3, gmax * 1.3], tickvals=tick_vals,
                                 ticktext=[cfmt(abs(v)) for v in tick_vals], title="◀ Exports    |    Imports ▶"),
                      yaxis=dict(autorange="reversed", tickvals=last.layout.yaxis.tickvals,
                                 ticktext=last.layout.yaxis.ticktext),
                      shapes=last.layout.shapes, annotations=last.layout.annotations,
                      legend=dict(orientation="h", y=-0.06), **play_controls([str(y) for y in years], 700, len(years) - 1))
    st.plotly_chart(fig)
    st.caption("Luxembourg is pinned to the top row; the number before each name is the country's rank by total trade. "
               "“Per inhabitant” divides by population (dashed lines = EU average). Goods only, not services.")
    ysel = st.select_slider("Table for year", options=years, value=years[-1], key="cmp_year")
    rows, rank = values_for(years.index(ysel))
    st.dataframe(pd.DataFrame([{"Rank": rank[c], "Country": f"{flag(c)} {name(c)}", "Exports": cfmt(ex), "Imports": cfmt(im),
                                "Balance": ("+" if ex >= im else "−") + cfmt(abs(ex - im)), "Total": cfmt(ex + im)}
                               for c, ex, im in rows]), hide_index=True, width="stretch")
