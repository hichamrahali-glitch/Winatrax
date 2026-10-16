# Understanding Luxembourg's International Trade

A static JavaScript app about Luxembourg's trade in goods, built on Eurostat Comext data (1999–2026). One page holds two charts:

- **World map**: Luxembourg's five largest trading partners over time, with the map zooming to them. Click a country to see the goods traded with it, then keep clicking to go from categories down to specific products.
- **Country comparison**: imports and exports per inhabitant for the 32 reporters of Eurostat's EU trade dataset (the 27 EU countries, the United Kingdom and 4 country groups), year by year, with Luxembourg pinned on top.

## Run

Open `index.html` in a browser (double-click it). No server, build tool or install is needed. The page loads D3, the world map outlines and a font from public CDNs, so it needs an internet connection.

The folder can also be published as-is, for example on GitHub Pages.

## Project layout

- `index.html`: one page: a start page (title, team in alphabetical order, trade illustration), an introduction with the three key questions, the world map, the country comparison and a methodology section, with a text navigation on the left that scrolls to each. The team names are in the `hero-people` list.
- `assets/world_map/`: world map (`map.js`, `map.css`).
- `assets/country_comparison/`: country comparison (`comparison.js`, `comparison.css`).
- `assets/shared/iso_codes.js`: country codes used to match trade partners to map shapes.
- `assets/app.js`, `assets/app.css`: page layout and the left navigation (smooth scrolling, highlights the section in view). Links such as `index.html#comparison`, `#world-map` or `#introduction` open on that section.
- `assets/img/trade-illustration.jpg`: start page illustration (Freepik, "Hand drawn international trade illustration"). Free Freepik images require the credit shown on the start page. `luxembourg-grund.jpg` is the earlier start page photo, no longer used.
- `assets/hs2_labels.json`: short name and icon per HS2 chapter, written by hand (a chapter missing here shows as "Chapter 27" without an icon).
- `data/derived/`: the prepared trade data (JSON), frozen.
- `data/js/`: the same data bundled as script files so the page can load it from disk. `core.js` and `details.js` load with the page; `products/<HS2>.js` loads when that category is opened in the partner chart under the map.
- `data/raw/`: inputs of the country comparison: `eu_trade_totals.json` (Eurostat Comext DS-045409, every reporter's trade with the world, all goods, imports and exports, value and weight, annual) and `wdi_population.csv` (World Bank World Development Indicators, SP.POP.TOTL, 1999–2025). When the Python pipeline runs it also caches one file per API request here (`api/`, `api_cn8/`), and writes the full Luxembourg tables to `data/processed/`; both are large and stay out of git.
- `scripts/build-data.mjs`: rebuilds `data/js/` from `data/derived/` and `data/raw/`, and writes `data/derived/trade_per_inhabitant.csv`.
- `scripts/ingestion/`, `scripts/processing/`: the Python pipeline that downloads the data from Eurostat and prepares `data/derived/`. `src/` holds what those commands share: `ingestion/eurostat_api.py` (API requests and JSON-stat parsing), `processing/trade_tree.py` (the HS2 > HS4 > HS6 > CN8 product tree) and `project_paths.py`.

## Data

The data in `data/derived/` is frozen: it was retrieved from Eurostat on 14–15 October 2026 and is committed, so the page needs nothing but a browser. The Python pipeline that downloaded it (`DS-045409`) and prepared `data/derived/` is in `scripts/` and `src/`, and can be run again whenever the data needs refreshing.

### Refreshing the data

Needs Python 3.11 or later and Node.js 18 or later:

```bash
pip install -r requirements.txt
```

Then, from the project root, in this order:

```bash
python -m scripts.ingestion.download_eurostat         # Luxembourg's trade, HS2 chapters, monthly and annual -> data/processed/
python -m scripts.ingestion.download_partner_detail   # product detail down to CN8 for the 40 largest partners, latest full year
python -m scripts.ingestion.download_country_totals   # every reporter's trade with the world -> data/raw/eu_trade_totals.json
python -m scripts.processing.build_app_data           # -> data/derived/app_data.json, data/derived/products/
python -m scripts.processing.build_partner_products   # -> data/derived/partner_products.json
python -m scripts.processing.build_partner_trees      # -> data/derived/partners/
node scripts/build-data.mjs                           # -> data/js/, data/derived/trade_per_inhabitant.csv
```

The first command is the long one: a request per product and frequency, about 300 MB of CSV. Every download is cached per request under `data/raw/`, so a run that stops can simply be started again; delete the cache folder to pick up new months. `build_app_data` reads the monthly table from `data/processed/` and `build_partner_products` the annual one; both, like `download_partner_detail`, take another copy of that file as their first argument. `build_partner_trees` reads the per-partner downloads in `data/raw/api_cn8/`.

Population is not downloaded: `data/raw/wdi_population.csv` is an export of the World Bank's SP.POP.TOTL series from [DataBank](https://databank.worldbank.org/source/world-development-indicators), one row per country and one column per year.

### Trade per inhabitant

For each reporter and year: imports per inhabitant = imports ÷ population, and exports per inhabitant = exports ÷ population, both by value (€) and by weight (tonnes). The four country groups in the dataset (EU, EU27_2020, euro area, euro area 21) have no trade with the world in Comext, so their trade and population are the sums of their member countries in that year; "members at the time" follows the accession dates in Eurostat's reporter labels. The United Kingdom reports until 2019. The full table is in `data/derived/trade_per_inhabitant.csv`.

`python -m scripts.ingestion.download_country_totals` downloads the trade totals; the same query without Python is:

```bash
curl -G "https://ec.europa.eu/eurostat/api/comext/dissemination/statistics/1.0/data/DS-045409" \
  --data-urlencode format=JSON -d partner=WORLD -d product=TOTAL -d freq=A -d sinceTimePeriod=1999 \
  -d flow=1 -d flow=2 -d indicators=VALUE_IN_EUROS -d indicators=QUANTITY_IN_100KG -o data/raw/eu_trade_totals.json
```

### Rebuilding the bundles

If anything in `data/derived/` or `data/raw/` changes, rebuild the files the page loads with Node.js 18 or later:

```bash
node scripts/build-data.mjs
```
