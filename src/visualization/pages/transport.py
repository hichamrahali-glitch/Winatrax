"""Streamlit renderer for the transport view."""
from __future__ import annotations

def render(ctx):
    st, pd, go = ctx.st, ctx.pd, ctx.go
    flag = ctx.flag
    MODE_NAMES, MODE_ICONS = ctx.MODE_NAMES, ctx.MODE_ICONS
    MODE_COLOURS = ctx.MODE_COLOURS
    load_transport = ctx.load_transport
    T = load_transport()
    st.subheader("How do Luxembourg's goods travel, and what does it cost the climate?")
    st.warning("The CO₂ figures are an **estimate** (tonnes × distance × GLEC emission factor). Customs record the "
               "transport mode only for trade with non-EU countries; for EU countries it is assumed from "
               "Luxembourg's national freight split. See the method below.")
    tflow = st.radio("Trade flow", ["Both", "Exports", "Imports"], horizontal=True, key="t_flow",
                     format_func=lambda f: "Exports + imports" if f == "Both" else f)
    S = T["summary"][tflow]
    modes = T["modes"]
    t_all, c_all = sum(S["all"]["tonnes"].values()), sum(S["all"]["co2"].values())

    def tf(t):
        return f"{t / 1e6:.1f} Mt" if t >= 1e6 else (f"{t / 1e3:,.0f} kt" if t >= 1e3 else f"{t:,.0f} t")

    k1, k2, k3 = st.columns(3)
    k1.metric(f"Estimated transport CO₂, {T['year']}", tf(c_all) + " CO₂e",
              help=f"{sum(S['eu']['co2'].values()) / c_all:.0%} from trade with EU countries")
    k2.metric("Air freight", f"{S['all']['co2']['air'] / c_all:.0%} of the CO₂",
              f"only {S['all']['tonnes']['air'] / t_all:.1%} of the tonnes", delta_color="off")
    k3.metric("Road freight", f"{S['all']['co2']['road'] / c_all:.0%} of the CO₂",
              f"{S['all']['tonnes']['road'] / t_all:.0%} of the tonnes", delta_color="off")

    scope = st.radio("Coverage", ["all", "extra"], horizontal=True, key="t_scope",
                     format_func=lambda s: "All trade" if s == "all" else "Non-EU trade only (mode measured)")
    part = S[scope]
    fig = go.Figure()
    for m in modes:
        tt, cc = sum(part["tonnes"].values()), sum(part["co2"].values())
        fig.add_bar(y=["Share of CO₂", "Share of tonnes"], x=[part["co2"][m] / cc * 100, part["tonnes"][m] / tt * 100],
                    orientation="h", name=f"{MODE_ICONS[m]} {MODE_NAMES[m]}", marker_color=MODE_COLOURS[m],
                    hovertemplate="%{x:.1f}%<extra>" + MODE_NAMES[m] + "</extra>")
    fig.update_layout(barmode="stack", height=230, margin=dict(l=10, r=10, t=10, b=10), xaxis=dict(range=[0, 100], ticksuffix="%"),
                      legend=dict(orientation="h", y=-0.25))
    st.plotly_chart(fig)
    factors = {f["mode"]: f["factor"] for f in T["factors"]}
    st.dataframe(pd.DataFrame([{
        "Mode": f"{MODE_ICONS[m]} {MODE_NAMES[m]}", "Goods (tonnes)": f"{part['tonnes'][m]:,.0f}",
        "CO₂ (t CO₂e)": "not estimated" if m == "other" else f"{part['co2'][m]:,.0f}",
        "kg CO₂ per tonne": "–" if m == "other" or not part["tonnes"][m] else f"{part['co2'][m] * 1000 / part['tonnes'][m]:,.0f}",
        "GLEC factor (g/t-km)": "788–1,363" if m == "air" else str(factors.get(m, "–"))}
        for m in modes if part["tonnes"][m] > 0]), hide_index=True, width="stretch")

    st.markdown("#### How do goods to and from non-EU countries travel? (measured)")
    tm = st.radio("Measure", ["value", "tonnes"], horizontal=True, key="t_trend",
                  format_func=lambda m: "By value (€)" if m == "value" else "By weight (tonnes)")
    flows = ["Exports", "Imports"] if tflow == "Both" else [tflow]
    fig = go.Figure()
    for m in modes:
        y = [sum(T["trend"][f][tm][m][i] for f in flows) for i in range(len(T["years"]))]
        fig.add_bar(x=T["years"], y=y, name=f"{MODE_ICONS[m]} {MODE_NAMES[m]}", marker_color=MODE_COLOURS[m])
    fig.update_layout(barmode="stack", height=380, margin=dict(l=10, r=10, t=10, b=10),
                      yaxis_title="million €" if tm == "value" else "tonnes", legend=dict(orientation="h", y=-0.15))
    st.plotly_chart(fig)

    def stacked_top(items, label):
        fig = go.Figure()
        ys = [label(d) for d in items]
        for m in ["road", "rail", "inland_waterway", "sea", "air"]:
            fig.add_bar(y=ys, x=[d["byMode"][m] / 1000 for d in items], orientation="h", name=f"{MODE_ICONS[m]} {MODE_NAMES[m]}",
                        marker_color=MODE_COLOURS[m], hovertemplate="%{x:,.1f} kt CO₂e<extra>" + MODE_NAMES[m] + "</extra>")
        fig.update_layout(barmode="stack", height=40 + 28 * len(items), margin=dict(l=10, r=10, t=10, b=10),
                          yaxis=dict(autorange="reversed"), xaxis_title="thousand tonnes CO₂e (estimated)",
                          legend=dict(orientation="h", y=-0.12))
        return fig

    st.markdown("#### Which partner countries cause the most transport CO₂? (estimate)")
    st.plotly_chart(stacked_top(S["partners"], lambda d: f"{flag(d['code'])} {d['name']} {'(EU, mode estimated)' if d['eu'] else '(non-EU)'}"))
    st.markdown("#### Which products (non-EU trade) cause the most transport CO₂? (estimate)")
    st.plotly_chart(stacked_top(S["products"], lambda d: f"{d['icon']} {d['name']}"))

    st.markdown("#### Context: Luxembourg, an air cargo hub (measured)")
    c = T["context"]
    a1, a2 = st.columns(2)
    a1.metric(f"Air freight through Luxembourg airport, {c['airport']['year']}", tf(c["airport"]["tonnes"]),
              f"Luxembourg's own non-EU trade by air: {tf(c['own_air_tonnes'])} ({c['own_air_tonnes'] / c['airport']['tonnes']:.0%})",
              delta_color="off")
    k = c["co2_accounts"]
    a2.metric(f"CO₂ of all industries in Luxembourg, {k['year']}", f"{k['air_transport'] / k['total']:.0%} from air transport",
              f"{tf(k['air_transport'])} of {tf(k['total'])} (covers flights worldwide)", delta_color="off")

    with st.expander("How these numbers are calculated", expanded=False):
        sp, A = T["split"]["shares"], T["assumptions"]
        st.markdown(f"""
    **Formula** (per partner country, flow and transport mode):
    `CO₂ (tonnes) = goods (tonnes) × distance (km) × emission factor (g CO₂e per tonne-km) ÷ 1,000,000`

    - **Goods:** Eurostat DS-045409, total goods, {T['year']}.
    - **Transport mode:** non-EU partners measured by customs (DS-059334); EU partners not recorded, so Luxembourg's inland freight
      modal split in {T['split']['year']} (tran_hv_frmod) is applied: road {sp['road']:.0%}, rail {sp['rail']:.0%}, inland waterway {sp['inland_waterway']:.0%}.
    - **Distance:** straight line from Luxembourg City to the partner's centre; road/rail/waterway × {A['detour_land']}; air straight line
      (GLEC adds 95 km); sea = {A['road_to_antwerp_km']} km truck to Antwerp + sea route × {A['detour_sea']}.
    - **Not included:** post, pipelines/power lines, self-propelled goods, unknown mode.
    - **Limits:** order-of-magnitude estimate; real routes, vehicles and load factors vary; goods only.
    """)
        st.dataframe(pd.DataFrame([{"Mode": f["mode"].replace("_", " "), "g CO₂e / t-km": f["factor"], "Source (GLEC Framework v3.1)": f["ref"]}
                                   for f in T["factors"]]), hide_index=True, width="stretch")
