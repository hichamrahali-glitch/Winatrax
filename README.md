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
- `data/derived/`: the prepared trade data (JSON), frozen.
- `data/js/`: the same data bundled as script files so the page can load it from disk. `core.js` and `details.js` load with the page; `products/<HS2>.js` loads when that category is opened in the partner chart under the map.
- `data/raw/`: inputs of the country comparison: `eu_trade_totals.json` (Eurostat Comext DS-045409, every reporter's trade with the world, all goods, imports and exports, value and weight, annual) and `wdi_population.csv` (World Bank World Development Indicators, SP.POP.TOTL, 1999–2025).
- `scripts/build-data.mjs`: rebuilds `data/js/` from `data/derived/` and `data/raw/`, and writes `data/derived/trade_per_inhabitant.csv`.

## Data

The data is frozen. The Python pipeline that downloaded it from Eurostat (`DS-045409` and related datasets) and prepared `data/derived/` has been removed; it is still in the git history if the data ever needs refreshing.

### Trade per inhabitant

For each reporter and year: imports per inhabitant = imports ÷ population, and exports per inhabitant = exports ÷ population, both by value (€) and by weight (tonnes). The four country groups in the dataset (EU, EU27_2020, euro area, euro area 21) have no trade with the world in Comext, so their trade and population are the sums of their member countries in that year; "members at the time" follows the accession dates in Eurostat's reporter labels. The United Kingdom reports until 2019. The full table is in `data/derived/trade_per_inhabitant.csv`.

To refresh the trade totals, download the same query again into `data/raw/eu_trade_totals.json`:

```bash
curl -G "https://ec.europa.eu/eurostat/api/comext/dissemination/statistics/1.0/data/DS-045409" \
  --data-urlencode format=JSON -d partner=WORLD -d product=TOTAL -d freq=A -d sinceTimePeriod=1999 \
  -d flow=1 -d flow=2 -d indicators=VALUE_IN_EUROS -d indicators=QUANTITY_IN_100KG -o data/raw/eu_trade_totals.json
```

### Rebuilding

If anything in `data/derived/` or `data/raw/` changes, rebuild the bundles with Node.js 18 or later:

```bash
node scripts/build-data.mjs
```

`data/derived/seasonality.json` and `data/derived/transport_data.json` are not used by the current views.
