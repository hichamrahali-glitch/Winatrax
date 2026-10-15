"""Streamlit renderer for the partner detail view."""
from __future__ import annotations

def render(ctx):
    st, pd, go = ctx.st, ctx.pd, ctx.go
    D, HS2 = ctx.D, ctx.HS2
    flag, name, fmt = ctx.flag, ctx.name, ctx.fmt
    measure, flow = ctx.measure, ctx.flow
    load_partner = ctx.load_partner
    GREY, COLOUR = ctx.GREY, ctx.COLOUR
    PD = D["partnerDetail"]
    year = PD["year"]
    prepared = [p["code"] for p in PD["list"]]
    live = [p["code"] for p in PD.get("live", [])]
    st.subheader("For a given partner country, what are the main goods traded with Luxembourg?")
    c1, c2 = st.columns([2, 1])
    partner = c1.selectbox("Partner country", prepared + live, key="partner",
                           format_func=lambda c: f"{flag(c)} {name(c)}" + ("" if c in prepared else "  (loaded live from Eurostat)"))
    share = c2.slider("Show items making up this share of trade", 50, 95, 80, 5, format="%d%%",
                      help="At every level, smaller items are grouped as “Other”.") / 100
    try:
        with st.spinner("Loading from Eurostat…" if partner in live else "Loading…"):
            pdata, source = load_partner(partner, year)
    except Exception as e:                                   # e.g. no internet for a live partner
        st.error(f"Could not load {name(partner)}: {e}")
        pdata = None
    if pdata:
        root = pdata[measure][flow]
        labels = pdata["labels"]
        exp = flow == "Exports"
        st.markdown(f"**{'Exports to' if exp else 'Imports from'} {flag(partner)} {name(partner)}, {year}: "
                    f"{fmt(root['v'], measure)}**" + ("  ·  _loaded live from the Eurostat API_" if source == "live" else ""))

        def node_label(code):
            if len(code) == 2:
                h = HS2.get(code, {"name": code, "icon": ""})
                return f"{h['icon']} {code} {h['name']}"
            text = labels.get(code, code)
            return f"{code} {text[:60] + '…' if len(text) > 60 else text}"

        ids, parents, texts, vals, hovers = [], [], [], [], []

        def walk(node, node_id, parent_id):
            """Add a node and its shown children; returns the value used for the node.
            Plotly treemaps draw nothing if a parent is smaller than the sum of its children,
            so a parent's value is computed from what is shown inside it (bottom-up)."""
            pos = len(ids)
            ids.append(node_id)
            parents.append(parent_id)
            vals.append(0)
            texts.append("All goods" if node["c"] == "TOTAL" else node_label(node["c"]))
            full = "All goods" if node["c"] == "TOTAL" else (HS2.get(node["c"], {}).get("full") if len(node["c"]) == 2 else labels.get(node["c"], node["c"]))
            hovers.append(f"{full}<br>{fmt(node['v'], measure)}")
            kids, shown, cum = node.get("k", []), [], 0.0
            for k in kids:
                if shown and cum >= share * node["v"]:
                    break
                shown.append(k)
                cum += k["v"]
            inside = sum(walk(k, f"{node_id}/{k['c']}", node_id) for k in shown)
            other_n = len(kids) - len(shown) + node.get("n", 0)
            other_v = round(node["v"] - cum, 6)
            if kids and other_v > 0 and other_n > 0:
                ids.append(f"{node_id}/other")
                parents.append(node_id)
                vals.append(other_v)
                texts.append(f"Other ({other_n} smaller items)")
                hovers.append(f"{other_n} smaller items grouped<br>{fmt(other_v, measure)}")
                inside += other_v
            vals[pos] = max(node["v"], inside * (1 + 1e-9))   # tiny margin for float sums
            return vals[pos]

        walk(root, "TOTAL", "")
        fig = go.Figure(go.Treemap(ids=ids, parents=parents, values=vals, labels=texts, branchvalues="total",
                                   maxdepth=2, hovertext=hovers, hoverinfo="text",
                                   texttemplate="%{label}<br>%{percentParent:.0%}",
                                   marker=dict(colors=[GREY if t.startswith("Other") else COLOUR for t in texts],
                                               line=dict(width=1, color="white")), pathbar=dict(visible=True)))
        fig.update_layout(height=620, margin=dict(l=0, r=0, t=30, b=0))
        st.plotly_chart(fig)
        st.caption("Click a box to go one level deeper: 2-digit chapters → 4-digit headings → 6-digit subheadings → "
                   "8-digit products (CN8). Click the bar at the top to go back up. Percentages are shares of the level above.")

        leaves = []

        def collect(node):
            if len(node["c"]) == 8:
                leaves.append(node)
            for k in node.get("k", []):
                collect(k)
        collect(root)
        if leaves:
            leaves.sort(key=lambda n: -n["v"])
            st.markdown("**Most significant 8-digit products**")
            st.dataframe(pd.DataFrame([{"CN8 code": n["c"], "Product": labels.get(n["c"], n["c"]),
                                        "Amount": fmt(n["v"], measure), "Share of total": f"{n['v'] / root['v']:.1%}"}
                                       for n in leaves[:15]]), hide_index=True, width="stretch")
