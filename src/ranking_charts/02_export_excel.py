"""Export the API download to Excel.

Excel allows max 1,048,576 rows per sheet, so:
  - annual  -> one sheet "annual" (+ "products", "partners" lookup sheets)
  - monthly -> one sheet per year ("1999", "2000", ...)

Input : data/processed/lu_trade_hs2_{annual,monthly}.csv.gz (from 00_)
Output: data/processed/lu_trade_hs2_annual.xlsx
        data/processed/lu_trade_hs2_monthly.xlsx

Run from the project root:  python python/02_export_excel.py
"""
import math
from pathlib import Path

import pandas as pd
import xlsxwriter

EXCEL_MAX_ROWS = 1_048_575  # minus header row
IN_DIR = Path("data/processed")


def read_trade(freq):
    # keep_default_na=False: partner code "NA" is Namibia, not a missing value
    df = pd.read_csv(IN_DIR / f"lu_trade_hs2_{freq}.csv.gz", dtype=str,
                     keep_default_na=False, na_values={"VALUE_IN_EUROS": [""], "QUANTITY_IN_100KG": [""]})
    for c in ("VALUE_IN_EUROS", "QUANTITY_IN_100KG"):
        df[c] = pd.to_numeric(df[c])
    return df.drop(columns="reporter")  # always LU


def lookups(df):
    return {
        "products": df[["product", "product_label"]].drop_duplicates().sort_values("product"),
        "partners": df[["partner", "partner_label"]].drop_duplicates().sort_values("partner"),
    }


def write_workbook(path, sheets):
    # Row-by-row in constant_memory mode: low memory for ~2 million rows.
    # (pandas.to_excel writes cells column-wise, which constant_memory drops.)
    wb = xlsxwriter.Workbook(str(path), {"constant_memory": True})
    bold = wb.add_format({"bold": True})
    for name, df in sheets.items():
        ws = wb.add_worksheet(name)
        ws.write_row(0, 0, list(df.columns), bold)
        for i, row in enumerate(df.itertuples(index=False, name=None), start=1):
            ws.write_row(i, 0, [None if isinstance(v, float) and math.isnan(v) else v for v in row])
    wb.close()


# ---- Annual: single data sheet ---------------------------------------------
annual = read_trade("annual")
assert len(annual) <= EXCEL_MAX_ROWS
write_workbook(IN_DIR / "lu_trade_hs2_annual.xlsx", {"annual": annual, **lookups(annual)})
print(f"Wrote annual workbook: {len(annual):,} rows")

# ---- Monthly: one sheet per year -------------------------------------------
monthly = read_trade("monthly")
by_year = {y: g for y, g in monthly.groupby(monthly["time"].str[:4], sort=True)}
too_big = [y for y, g in by_year.items() if len(g) > EXCEL_MAX_ROWS]
if too_big:
    raise SystemExit(f"Years exceed Excel's row limit: {', '.join(too_big)}")
write_workbook(IN_DIR / "lu_trade_hs2_monthly.xlsx", {**by_year, **lookups(monthly)})
print(f"Wrote monthly workbook: {len(monthly):,} rows across {len(by_year)} year sheets")
