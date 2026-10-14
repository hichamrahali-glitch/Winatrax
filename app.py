
import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(
    page_title="Luxembourg Beyond Its Borders",
    layout="wide"
)

st.title("Luxembourg Beyond Its Borders")

df = pd.read_csv("data/trade.csv")

tab1, tab2, tab3, tab4 = st.tabs([
    "Trade Overview",
    "Trade Impacts",
    "What If?",
    "Future Outlook"
])

with tab1:
    st.header("What does Luxembourg trade?")
    # KPI cards, timeline and product charts

with tab2:
    st.header("What is the impact of trade?")
    # Dependency and supported impact charts

with tab3:
    st.header("Could Luxembourg trade differently?")
    # Sliders and before/after comparisons

with tab4:
    st.header("What could the future look like?")
    # Historical data and illustrative scenarios
