"""Prepare and render the data contract for the standalone D3 world map.

The HTML, CSS and JavaScript live in assets/world_map/. Prepared dashboard data
comes from data/derived/; this module adapts it for Streamlit's HTML component.
"""
import json
from pathlib import Path

from project_paths import ASSETS_DIR, DERIVED_DATA_DIR
from visualization.world_map.iso_codes import iso_numeric

MAP_ASSETS = ASSETS_DIR / "world_map"
TEMPLATE = MAP_ASSETS / "index.html"
STYLES = MAP_ASSETS / "map.css"
SCRIPT = MAP_ASSETS / "map.js"
PARTNER_PRODUCTS = DERIVED_DATA_DIR / "partner_products.json"
PARTNER_TREES = DERIVED_DATA_DIR / "partners"
MARKER = "/*__DATA__*/null"
KEEP = 10


def load_partner_products():
    if PARTNER_PRODUCTS.exists():
        return json.loads(PARTNER_PRODUCTS.read_text(encoding="utf-8"))
    return {"years": [], "partners": {}}


def short(label, n=120):
    return label if len(label) <= n else label[:n - 1].rstrip(" ,;") + "…"


def load_product_detail(top=5):
    """Product trees of the prepared partners, cut to the top items at every level:
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
    html = TEMPLATE.read_text(encoding="utf-8")
    css = STYLES.read_text(encoding="utf-8")
    js = SCRIPT.read_text(encoding="utf-8").replace(
        MARKER, json.dumps(data, ensure_ascii=False, separators=(",", ":")))
    if "<!-- WORLD_MAP_STYLES -->" not in html or "<!-- WORLD_MAP_SCRIPT -->" not in html:
        raise ValueError("World map template is missing its CSS or JavaScript insertion point")
    return (html.replace("<!-- WORLD_MAP_STYLES -->", f"<style>\n{css}\n</style>")
            .replace("<!-- WORLD_MAP_SCRIPT -->", f"<script>\n{js}\n</script>"))


def write_standalone(D, blobs, product_label, measure="value", flow="Exports", target=None):
    target = target or DERIVED_DATA_DIR / "top5_map.html"
    target.parent.mkdir(parents=True, exist_ok=True)
    content = page(map_data(D, blobs, product_label, measure, flow))
    target.write_text(content, encoding="utf-8")
    return target


def render(D, blobs, product_label, measure, flow, height=860):
    import streamlit as st
    import streamlit.components.v1 as components
    pp, trees = st.cache_data(load_partner_products)(), st.cache_data(load_product_detail)()
    components.html(page(map_data(D, blobs, product_label, measure, flow, pp, trees)), height=height, scrolling=False)


