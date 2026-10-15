"""Animated map of Luxembourg's top 5 trading partners (D3, assets/top5_map.html).

In the app:   top5_map.render(D, blobs, product_label, measure, flow)  (World map tab of monica_app.py)
Standalone:   python top5_map.py [HS2 code]  ->  output/top5_map.html  (all goods by default)

Data: the per-period partner rankings already prepared for the race charts
(output/app_data.json and output/products/<code>.json). Only the top 10 partners per
period are sent to the page: 5 are mapped, ranks 6-10 show up in the hover text.
Clicking a country shows its main HS2 chapters from output/partner_products.json
(src/ranking_charts/10_build_partner_products.py); without that file the click view
shows totals only. Clicking a chapter there opens its main products, and each product
can be opened further (HS4 > HS6 > CN8), from the prepared partner trees in
output/partners/<code>.json (40 partners, one year).
"""
import json
import sys
from pathlib import Path

from iso_codes import iso_numeric

ROOT = Path(__file__).parent
TEMPLATE = ROOT / "assets" / "top5_map.html"
PARTNER_PRODUCTS = ROOT / "output" / "partner_products.json"
PARTNER_TREES = ROOT / "output" / "partners"
MARKER = "/*__DATA__*/null"
KEEP = 10


def load_partner_products():
    if PARTNER_PRODUCTS.exists():
        return json.loads(PARTNER_PRODUCTS.read_text(encoding="utf-8"))
    return {"years": [], "partners": {}}


def short(label, n=120):
    return label if len(label) <= n else label[:n - 1].rstrip(" ,;") + "…"


def load_product_detail(top=20):
    """Product trees of the prepared partners (already limited to the main items at every level
    when they were built), up to `top` children per node:
    {"partners": {code: {"year", "m": {"measure|flow": {hs2: node}}}}, "labels": {code: text}},
    node = [code, amount, [child nodes]] going HS2 > HS4 > HS6 > CN8. Labels are shared
    across partners (the same CN8 text appears for many of them)."""
    partners, labels = {}, {}

    def cut(n, src):
        if len(n["c"]) > 2 and n["c"] in src:
            labels[n["c"]] = short(src[n["c"]])
        return [n["c"], n["v"], [cut(k, src) for k in n.get("k", [])[:top]]]

    for f in sorted(PARTNER_TREES.glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        src = d.get("labels", {})
        m = {f"{measure}|{flow}": {ch["c"]: cut(ch, src) for ch in d.get(measure, {}).get(flow, {}).get("k", [])}
             for measure in ("value", "quantity") for flow in ("Exports", "Imports")}
        partners[f.stem] = {"year": int(d["year"]), "m": m}
    return {"partners": partners, "labels": labels}


def map_data(D, blobs, product_label, measure="value", flow="Exports", pp=None, trees=None):
    """blobs: {measure: {flow: {"frames": [[code, value, prev_rank], ...] per period, "world": [...]}}}."""
    pp = pp or load_partner_products()
    trees = load_product_detail() if trees is None else trees
    series, codes = {}, set(pp["partners"])
    for m, by_flow in blobs.items():
        for f, b in by_flow.items():
            frames = [[[c, v, prev] for c, v, prev in fr[:KEEP]] for fr in b["frames"]]
            series[f"{m}|{f}"] = {"frames": frames, "world": b["world"]}
            codes |= {c for fr in frames for c, _, _ in fr}
    return {"frames": D["frames"], "series": series, "product": product_label,
            "names": {c: D["names"].get(c, c) for c in codes},
            "ids": {c: iso_numeric(c) for c in codes if iso_numeric(c)},
            "init": {"measure": measure, "flow": flow},
            "pp": pp["partners"], "ppYears": pp["years"], "trees": trees["partners"], "labels": trees["labels"],
            "hs2": {c: {k: h[k] for k in ("name", "icon", "full") if k in h} for c, h in D["hs2"].items()}}


def page(data):
    return TEMPLATE.read_text(encoding="utf-8").replace(
        MARKER, json.dumps(data, ensure_ascii=False, separators=(",", ":")))


def render(D, blobs, product_label, measure, flow, height=860):
    import streamlit as st
    import streamlit.components.v1 as components
    pp, trees = st.cache_data(load_partner_products)(), st.cache_data(load_product_detail)()
    components.html(page(map_data(D, blobs, product_label, measure, flow, pp, trees)), height=height, scrolling=False)


if __name__ == "__main__":
    out = ROOT / "output"
    D = json.loads((out / "app_data.json").read_text(encoding="utf-8"))
    code = sys.argv[1] if len(sys.argv) > 1 else "TOTAL"
    if code == "TOTAL":
        blobs, label = {m: D["measures"][m]["total"] for m in ("value", "quantity")}, "all goods"
    else:
        prod = json.loads((out / "products" / f"{code}.json").read_text(encoding="utf-8"))
        blobs, label = {m: prod[m] for m in ("value", "quantity")}, D["hs2"].get(code, {}).get("name", code).lower()
    target = out / "top5_map.html"
    target.write_text(page(map_data(D, blobs, label)), encoding="utf-8")
    print(f"{target}: {target.stat().st_size / 1e6:.2f} MB")
