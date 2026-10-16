"""Helpers for the Eurostat Comext dissemination API.

Docs: https://wikis.ec.europa.eu/display/EUROSTATHELP/API+Statistics+-+data+query

    comext_get("DS-045409", [("reporter", "LU"), ("product", "TOTAL"), ...], cache_file)

returns a long DataFrame with one column per dimension plus `value`.
Pass a parameter several times to request several codes, e.g.
[("flow", 1), ("flow", 2)].
"""
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests

COMEXT_BASE = "https://ec.europa.eu/eurostat/api/comext/dissemination/statistics/1.0/data/"

# Partner codes that are aggregates rather than countries.
AGGREGATES = ["WORLD", "EXT_EA", "EXT_EA21", "EXT_EU", "EXT_EU27_2020",
              "INT_EA", "INT_EA21", "INT_EU", "INT_EU27_2020"]

# Partner codes that are not countries either: stores and provisions, confidential
# trade and "not specified" (QQ-QZ), plus Ceuta/Melilla (XC) and Kosovo-era XL.
NOT_COUNTRIES = set(AGGREGATES) | {"QQ", "QR", "QS", "QU", "QV", "QW", "QX", "QY", "QZ", "XC", "XL"}


class QueryTooLarge(Exception):
    """Eurostat queues large queries asynchronously (HTTP 413): split them up."""


def comext_fetch(dataset, params, cache_file):
    """Download (or reuse the cached) JSON-stat response.

    Returns the cache path, or None if the query matches no data.
    """
    cache_file = Path(cache_file)
    if cache_file.exists():
        return cache_file
    cache_file.parent.mkdir(parents=True, exist_ok=True)

    for attempt in range(1, 6):
        try:
            res = requests.get(COMEXT_BASE + dataset,
                               params=[("format", "JSON")] + list(params), timeout=300)
        except requests.RequestException:
            res = None
        if res is not None:
            if res.status_code == 200:
                cache_file.write_bytes(res.content)
                return cache_file
            if res.status_code in (400, 404):   # e.g. HS chapter 77 is reserved
                return None
            if res.status_code == 413:
                raise QueryTooLarge("Query too large for a synchronous response - split it up.")
        time.sleep(10 * attempt)
    print(f"Warning: failed after retries: {cache_file}")
    return None


def comext_parse(file, labels=True):
    """JSON-stat -> long DataFrame.

    Values are stored as {flat_index: value}; the flat index is row-major over
    the dimensions listed in `id` with sizes in `size`.
    """
    d = json.loads(Path(file).read_text(encoding="utf-8"))
    if not d.get("value"):
        return None

    ids, sizes = d["id"], d["size"]
    codes = []
    for k in ids:
        index = d["dimension"][k]["category"]["index"]
        codes.append(np.array(sorted(index, key=index.get), dtype=object))

    flat = np.fromiter((int(i) for i in d["value"]), dtype=np.int64, count=len(d["value"]))
    out = pd.DataFrame({"value": np.fromiter(d["value"].values(), dtype=float, count=len(flat))})
    positions = np.unravel_index(flat, sizes)
    for k, c, pos in zip(ids, codes, positions):
        out[k] = c[pos]

    if labels:
        for k in ("partner", "product"):
            if k in ids:
                out[k + "_label"] = out[k].map(d["dimension"][k]["category"]["label"])
    return out


def comext_get(dataset, params, cache_file):
    f = comext_fetch(dataset, params, cache_file)
    return None if f is None else comext_parse(f)
