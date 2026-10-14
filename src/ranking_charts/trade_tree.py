"""Product tree for one partner country: HS2 > HS4 > HS6 > CN8.

Used by 04_build_race_page.py (prepared partners) and by app.py (any partner,
fetched live from the Eurostat API). At every level we keep the children that
make up KEEP_SHARE of their parent (at least KEEP_MIN, at most KEEP_MAX); the
rest is summed into "other", so only the most significant flows are shown.

Tree node: {"c": code, "v": value, "k": [children], "o": other value, "n": number of grouped items}
"""
import re

import requests

from eurostat_api import COMEXT_BASE, comext_parse

KEEP_SHARE, KEEP_MIN, KEEP_MAX = 0.95, 3, 20
# measure -> (Eurostat indicator, divisor to the stored unit, decimals kept)
MEASURES = {
    "quantity": ("QUANTITY_IN_100KG", 1e4, 2),   # 100 kg -> thousand tonnes
    "value":    ("VALUE_IN_EUROS",    1e6, 3),   # EUR -> million EUR
}


def num(v, digits=2):
    """Round, and write whole numbers without '.0' to keep the JSON small."""
    v = round(float(v), digits)
    return int(v) if v.is_integer() else v


def clean_label(text):
    # labels can list several versions: "current label(2002-2500);older label(1988-2001)"
    return re.split(r"\(\d{4}-\d{4}\);?", text)[0].strip()


def product_tree(values, digits, keep_share=KEEP_SHARE, keep_min=KEEP_MIN, keep_max=KEEP_MAX):
    """values: Series code -> value (digit-only codes of length 2/4/6/8, plus 'TOTAL').
    Returns (tree, set of codes used)."""
    values = values[values > 0]
    kids = {}
    for code in values.index:
        if code == "TOTAL" or not code.isdigit() or len(code) not in (2, 4, 6, 8):
            continue
        parent = "TOTAL" if len(code) == 2 else code[:len(code) - 2]
        kids.setdefault(parent, []).append(code)
    root_v = values.get("TOTAL", values[[c for c in kids.get("TOTAL", [])]].sum())
    used = set()

    def build(code, v):
        children = sorted(kids.get(code, []), key=lambda c: -values[c])
        node = {"c": code, "v": num(v, digits)}
        kept, cum = [], 0.0
        for c in children:
            if len(kept) >= keep_max or (len(kept) >= keep_min and cum >= keep_share * v):
                break
            kept.append(c)
            cum += values[c]
        if kept:
            used.update(kept)
            node["k"] = [build(c, values[c]) for c in kept]
            # "other" from the rounded figures, so children + other add up to the node exactly
            other = round(node["v"] - sum(k["v"] for k in node["k"]), digits)
            if other > 0:
                node["o"] = num(other, digits)
                node["n"] = len(children) - len(kept)   # how many smaller items are grouped
        return node

    return build("TOTAL", root_v), used


def partner_detail(df, year):
    """Long DataFrame from comext_parse (one partner, one year, all products) -> page data."""
    out, used_all = {"year": str(year)}, set()
    for name, (col, divisor, digits) in MEASURES.items():
        out[name] = {}
        for fl_code, fl in (("2", "Exports"), ("1", "Imports")):
            x = df[(df["flow"] == fl_code) & (df["indicators"] == col)].groupby("product")["value"].sum() / divisor
            tree, used = product_tree(x, digits)
            out[name][fl] = tree
            used_all |= used
    lab = df.drop_duplicates("product").set_index("product")["product_label"]
    out["labels"] = {c: clean_label(lab[c]) for c in sorted(used_all) if len(c) > 2 and c in lab.index}
    return out


def fetch_partner_live(partner, year, timeout=120):
    """Any partner country, straight from the Eurostat API (one request)."""
    params = [("format", "JSON"), ("reporter", "LU"), ("partner", partner), ("freq", "A"), ("time", str(year)),
              ("flow", 1), ("flow", 2), ("indicators", "VALUE_IN_EUROS"), ("indicators", "QUANTITY_IN_100KG")]
    res = requests.get(COMEXT_BASE + "DS-045409", params=params, timeout=timeout)
    res.raise_for_status()
    import json, tempfile, os
    with tempfile.NamedTemporaryFile("wb", suffix=".json", delete=False) as f:
        f.write(res.content)
        path = f.name
    try:
        df = comext_parse(path)
    finally:
        os.unlink(path)
    if df is None:
        raise ValueError(f"No data for {partner} in {year}")
    return partner_detail(df, year)
