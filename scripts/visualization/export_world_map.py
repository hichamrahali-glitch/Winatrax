"""Export the D3 world map as a self-contained HTML page."""
import json
import sys

from scripts._bootstrap import PROJECT_ROOT
from project_paths import DERIVED_DATA_DIR
from visualization.world_map.adapter import write_standalone


def main():
    data = json.loads((DERIVED_DATA_DIR / "app_data.json").read_text(encoding="utf-8"))
    code = sys.argv[1] if len(sys.argv) > 1 else "TOTAL"
    if code == "TOTAL":
        blobs = {measure: data["measures"][measure]["total"] for measure in ("value", "quantity")}
        label = "all goods"
    else:
        product = json.loads((DERIVED_DATA_DIR / "products" / f"{code}.json").read_text(encoding="utf-8"))
        blobs = {measure: product[measure] for measure in ("value", "quantity")}
        label = data["hs2"].get(code, {}).get("name", code).lower()

    target = write_standalone(data, blobs, label)
    print(f"Wrote {target} ({target.stat().st_size / 1e6:.2f} MB)")


if __name__ == "__main__":
    main()
