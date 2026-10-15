# Luxembourg Trade Explorer

Streamlit dashboard and analysis scripts for Luxembourg's goods trade. The data workflow is split into four steps:

```text
Eurostat API -> data/raw -> data/processed -> data/derived -> app.py
```

## Project Layout

- `scripts/ingestion/`: commands that download Eurostat source data and cache API responses.
- `src/ingestion/`: reusable Eurostat API client and parsing code.
- `scripts/processing/`: commands that clean, aggregate, and build datasets used by the app.
- `src/processing/`: reusable trade transformations, including partner product trees.
- `scripts/visualization/`: commands that create standalone charts or export the world map.
- `src/visualization/pages/`: Streamlit tab renderers.
- `src/visualization/charts/`: shared Plotly and Matplotlib chart helpers.
- `src/visualization/world_map/`: Python data adapter and country-code mapping for the D3 map.
- `assets/world_map/`: map HTML shell, JavaScript, and CSS.
- `data/raw/`: downloaded API responses and other source snapshots.
- `data/processed/`: normalized annual and monthly trade tables.
- `data/derived/`: app-ready JSON and generated visualizations.

`app.py` is the Streamlit entry point. It loads page renderers from `src/visualization/` and reads prepared data from `data/derived/`.

## Setup

Use Python 3.13 and install the pinned project dependencies:

```bash
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

## Build Data

Run commands from the repository root. Downloads are cached under `data/raw/`; rerunning a download reuses cached responses.

```bash
.venv/bin/python -m scripts.ingestion.download_eurostat
.venv/bin/python -m scripts.ingestion.download_partner_detail
.venv/bin/python -m scripts.ingestion.download_country_totals
.venv/bin/python -m scripts.ingestion.download_transport

.venv/bin/python -m scripts.processing.build_race_page
.venv/bin/python -m scripts.processing.build_transport_data
.venv/bin/python -m scripts.processing.build_seasonality_data
.venv/bin/python -m scripts.processing.build_partner_products
```

The first command writes annual and monthly tables to `data/processed/`. The processing commands create the dashboard inputs under `data/derived/`. To refresh source data, remove the corresponding cache directory under `data/raw/` and rerun its ingestion command.

Optional exports:

```bash
.venv/bin/python -m pip install -r requirements-optional.txt
.venv/bin/python -m scripts.processing.export_excel
.venv/bin/python -m scripts.visualization.trade_partners
.venv/bin/python -m scripts.visualization.top20_quantity
.venv/bin/python -m scripts.visualization.export_world_map
```

## Run The App

```bash
.venv/bin/streamlit run app.py
```

The dashboard uses prepared partner detail when available. For a partner without a prepared detail file, the partner detail view queries Eurostat live.
