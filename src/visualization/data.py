"""Cached access to prepared dashboard data and the optional live partner lookup."""
import json

import streamlit as st

from processing.trade_tree import fetch_partner_live
from project_paths import DERIVED_DATA_DIR


@st.cache_data
def load_app_data():
    return json.loads((DERIVED_DATA_DIR / "app_data.json").read_text(encoding="utf-8"))


@st.cache_data
def load_product(code):
    path = DERIVED_DATA_DIR / "products" / f"{code}.json"
    return json.loads(path.read_text(encoding="utf-8"))


@st.cache_data(show_spinner=False)
def load_partner(code, year):
    path = DERIVED_DATA_DIR / "partners" / f"{code}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8")), "prepared"
    return fetch_partner_live(code, year), "live"


@st.cache_data
def load_transport():
    path = DERIVED_DATA_DIR / "transport_data.json"
    return json.loads(path.read_text(encoding="utf-8"))
