"""Formatting and time-selection helpers shared by dashboard pages."""
import pandas as pd


def flag(code):
    """Emoji flag from a two-letter code."""
    code = {"EL": "GR", "UK": "GB", "XS": "RS"}.get(code, code)
    if len(code) != 2 or not code.isalpha():
        return ""
    return "".join(chr(0x1F1E6 + ord(ch) - 65) for ch in code.upper())


def country_name(code, names):
    return names.get(code, code)


def format_value(value, measure):
    """Format stored units: thousand tonnes for quantity, million EUR for value."""
    if value is None:
        return "–"
    if measure == "value":
        if value >= 1000:
            return f"€{value / 1000:.1f} bn"
        if value >= 1:
            return f"€{value:.0f} m" if value >= 100 else f"€{value:.1f} m"
        return f"€{value * 1000:.0f} k"
    if value >= 1000:
        return f"{value / 1000:.1f} Mt"
    if value >= 10:
        return f"{value:.0f} kt"
    if value >= 0.01:
        return f"{value:.2f} kt"
    return f"{value * 1000:.0f} t"


def period_label(index, frames):
    year, month = frames[index].split("-")
    return f"12 months to {pd.Timestamp(int(year), int(month), 1):%b %Y}"


def frame_indices(step, frames):
    count = len(frames)
    if step == "Monthly":
        indices = list(range(count))
    elif step == "Quarterly":
        indices = [i for i, frame in enumerate(frames) if frame[5:] in ("03", "06", "09", "12")]
    else:
        indices = [i for i, frame in enumerate(frames) if frame[5:] == "12"]
    return indices if indices[-1] == count - 1 else indices + [count - 1]
