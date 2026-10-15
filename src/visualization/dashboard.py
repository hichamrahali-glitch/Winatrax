"""Story-led views of Luxembourg's changing trade portfolio.

Run from the project root:
    .venv/bin/streamlit run app.py

Reads prepared dashboard data from data/derived/. Partner countries without
prepared detail are fetched live from Eurostat.
"""
from types import SimpleNamespace
import base64

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from project_paths import ASSETS_DIR
from visualization import seasonality
from visualization.charts.animated import big_period_label, play_controls
from visualization.data import load_app_data
from visualization.formatting import (
    country_name, flag, format_value,
)
from visualization.world_map import adapter as top5_map

EXPORT_COL, IMPORT_COL = "#2a78d6", "#eb6834"

from visualization.pages import country_comparison, seasonality_page, world_map


def main():
    st.set_page_config(page_title="Luxembourg trade explorer", page_icon="🇱🇺", layout="wide")
    hero_image = base64.b64encode((ASSETS_DIR / "images" / "luxembourg-hero.jpg").read_bytes()).decode("ascii")
    st.markdown("""
        <style>
        [data-testid="stHeader"] { display: none; }
        [data-testid="stMain"] { padding: 0; }
        [data-testid="stMainBlockContainer"] {
            max-width: none;
            padding: 0;
        }
        .st-key-story-hero {
            box-sizing: border-box;
            width: 100%;
            min-height: 100vh;
            margin: 0;
            padding: 3rem max(2rem, calc((100vw - 1280px) / 2));
            display: flex;
            align-items: center;
            color: #fff;
            background-color: rgba(5, 20, 34, .24);
            background-blend-mode: multiply;
            background-position: center 48%;
            background-size: cover;
        }
        .st-key-story-hero > div[data-testid="stVerticalBlock"] { width: 100%; }
        .hero-copy { max-width: 800px; }
        .hero-title { max-width: 17ch; margin: 0; font-size: 3.8rem; line-height: 1.04; font-weight: 700; }
        .hero-credits { margin-top: 2rem; padding-top: 1rem; border-top: 1px solid rgba(255,255,255,.48); }
        .hero-names { font-size: 1.05rem; line-height: 1.6; }
        .hero-institution { margin-top: .25rem; color: rgba(255,255,255,.82); font-size: .95rem; }
        .st-key-story-hero .hero-begin { display: inline-flex; gap: 1.25rem; align-items: center; margin-top: 2rem;
                      padding: .85rem 1.15rem; border-radius: 3px; background: #b51f3c; color: #fff !important;
                      font-weight: 700; text-decoration: none !important; }
        .st-key-story-hero .hero-begin:hover { background: #92182f; color: #fff !important; }
        .hero-begin:focus-visible { outline: 3px solid #fff; outline-offset: 3px; }
        .st-key-story-map, .st-key-story-comparison, .st-key-story-seasonality {
            box-sizing: border-box;
            width: 100%;
            max-width: 1280px;
            margin-inline: auto;
            min-height: 92vh;
            padding: 2.5rem 2rem 4rem;
            border-bottom: 1px solid rgba(128, 133, 144, .35);
        }
        @keyframes story-reveal {
            from { opacity: 0; transform: translateY(2rem); }
            to { opacity: 1; transform: translateY(0); }
        }
        @supports (animation-timeline: view()) {
            .st-key-story-map, .st-key-story-comparison, .st-key-story-seasonality {
                animation: story-reveal linear both;
                animation-timeline: view();
                animation-range: entry 0% entry 38%;
            }
        }
        @media (prefers-reduced-motion: reduce) {
            .st-key-story-map, .st-key-story-comparison, .st-key-story-seasonality {
                animation: none !important;
            }
        }
        .story-kicker { color: #68717d; font-size: 12px; font-weight: 700;
                        text-transform: uppercase; }
        @media (max-width: 700px) {
            .st-key-story-hero { min-height: 100svh; padding: 2rem 1.25rem; background-position: 62% center; }
            .hero-title { max-width: 17ch; font-size: 2.5rem; }
            .st-key-story-map, .st-key-story-comparison, .st-key-story-seasonality {
                min-height: 0;
                padding: 1.5rem 1.25rem 2.5rem;
            }
        }
        </style>
        """, unsafe_allow_html=True)

    # ---- data -------------------------------------------------------------------
    D = load_app_data()
    NAMES = D["names"]

    name = lambda code: country_name(code, NAMES)
    fmt = format_value

    st.markdown(f"""
        <style>
        .st-key-story-hero {{
            background-image: url("data:image/jpeg;base64,{hero_image}");
        }}
        </style>
        """, unsafe_allow_html=True)
    with st.container(key="story-hero"):
        st.markdown("""
            <div class="hero-copy">
              <h1 class="hero-title">How Luxembourg's trade portfolio changes</h1>
              <div class="hero-credits">
                <div class="hero-names">Hicham Rahali · Monica Pereira Henriques · Silvana Belegu</div>
                <div class="hero-institution">SnT · FINATRAX Group</div>
              </div>
              <a class="hero-begin" href="#story-map"><span>Begin</span><span aria-hidden="true">↓</span></a>
            </div>
            """, unsafe_allow_html=True)

    st.markdown('<div id="story-map"></div>', unsafe_allow_html=True)
    with st.container(key="story-map"):
        st.markdown('<div class="story-kicker">01 / Partners and geography</div>', unsafe_allow_html=True)
        st.header("Who does Luxembourg trade with?")
        st.caption("Follow the leading export and import partners over time, and explore where they are.")
        st.caption("Source: Eurostat (Comext DS-045409 and others). Values cover the previous 12 months; "
                   "quantities are in tonnes (Eurostat reports units of 100 kg).")
        map_ctx = SimpleNamespace(
            st=st, D=D, top5_map=top5_map,
        )
        world_map.render(map_ctx)

    with st.container(key="story-comparison"):
        st.markdown('<div class="story-kicker">02 / Luxembourg in Europe</div>', unsafe_allow_html=True)
        st.header("How does Luxembourg compare with other EU countries?")
        st.caption("Compare total trade or trade per inhabitant, and see where Luxembourg sits among its peers.")
        comparison_ctx = SimpleNamespace(
            st=st, pd=pd, go=go, D=D, flag=flag, name=name, fmt=fmt,
            big_period_label=big_period_label, play_controls=play_controls,
            EXPORT_COL=EXPORT_COL, IMPORT_COL=IMPORT_COL,
        )
        country_comparison.render(comparison_ctx)

    with st.container(key="story-seasonality"):
        st.markdown('<div class="story-kicker">03 / The rhythm of trade</div>', unsafe_allow_html=True)
        st.header("When does Luxembourg trade?")
        st.caption("Look past annual totals to the recurring monthly patterns in exports and imports.")
        seasonality_ctx = SimpleNamespace(st=st, seasonality=seasonality)
        seasonality_page.render(seasonality_ctx)
