// Bundle the prepared trade data in data/derived/ into script files the app can load
// straight from disk (index.html opened by double-click, no web server needed).
//
//   node scripts/build-data.mjs
//
// Writes data/js/:
//   core.js            window.LUX           frames, country names, HS2 names, product list,
//                                            total-goods partner rankings, country comparison
//   details.js         window.LUX_DETAILS   per-partner HS2 breakdown by year, and product
//                                            trees (HS2 > HS4 > HS6 > CN8) with shared labels
//   products/<hs2>.js  window.LUX_PRODUCTS  partner rankings for one HS2 chapter (loaded on demand)
//
// The country comparison is computed here from two raw files in data/raw/:
//   eu_trade_totals.json  Eurostat Comext DS-045409 ("EU trade since 1988"), every reporter's trade
//                         with the world, all goods, imports and exports, value and weight, annual
//   wdi_population.csv    World Bank World Development Indicators, SP.POP.TOTL (population, total)
// imports per inhabitant = imports / population (same for exports), for all 32 reporters. The 4 group
// reporters (EU, EU27_2020, EA, EA21) have no trade with WORLD in Comext, so their trade and
// population are the sums over their members in each year. It also writes the result as
// data/derived/trade_per_inhabitant.csv.
//
// The data in data/derived/ is frozen: the Python pipeline that downloaded it from Eurostat has
// been removed (it is in the git history). Re-run this script only if those JSON files change.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const SRC = path.join(ROOT, "data", "derived");
const OUT = path.join(ROOT, "data", "js");
const KEEP_PARTNERS = 10;   // partners per period sent to the map: 5 drawn, 6-10 behind "show more"
const KEEP_CHILDREN = 20;   // product tree children per node
const LABEL_MAX = 120;

const read = f => JSON.parse(fs.readFileSync(path.join(SRC, f), "utf8"));
const write = (f, global, data, key) => {
  const target = path.join(OUT, f);
  fs.mkdirSync(path.dirname(target), { recursive: true });
  const json = JSON.stringify(data);
  const body = key === undefined ? `window.${global} = ${json};\n`
    : `window.${global} = window.${global} || {};\nwindow.${global}[${JSON.stringify(key)}] = ${json};\n`;
  fs.writeFileSync(target, body);
  return body.length;
};
const short = s => (s.length <= LABEL_MAX ? s : s.slice(0, LABEL_MAX - 1).replace(/[ ,;]+$/, "") + "…");

// {measure: {flow: {frames, world, ...}}} -> {"measure|flow": {frames: top partners, world}}
function slimSeries(blobs) {
  const out = {};
  for (const [m, byFlow] of Object.entries(blobs))
    for (const [f, b] of Object.entries(byFlow))
      out[`${m}|${f}`] = { frames: b.frames.map(fr => fr.slice(0, KEEP_PARTNERS)), world: b.world };
  return out;
}

// ---- country comparison: trade per inhabitant -----------------------------------------------
const RAW = path.join(ROOT, "data", "raw");
const YEAR0 = 1999, YEAR1 = 2025;   // population runs to 2025; Comext's 2026 is a partial year
const YEARS = Array.from({ length: YEAR1 - YEAR0 + 1 }, (_, k) => YEAR0 + k);

function parseCsv(text) {   // RFC 4180: quoted fields may contain commas and doubled quotes
  const rows = []; let row = [], f = "", q = false;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (q) { if (ch === '"' && text[i + 1] === '"') { f += '"'; i++; } else if (ch === '"') q = false; else f += ch; }
    else if (ch === '"') q = true;
    else if (ch === ",") { row.push(f); f = ""; }
    else if (ch === "\n" || ch === "\r") { if (ch === "\r" && text[i + 1] === "\n") i++; row.push(f); rows.push(row); row = []; f = ""; }
    else f += ch;
  }
  if (f || row.length) { row.push(f); rows.push(row); }
  return rows;
}

// Country codes: load the browser module with a stand-in window object
const isoCtx = { window: {} };
new Function("window", fs.readFileSync(path.join(ROOT, "assets", "shared", "iso_codes.js"), "utf8"))(isoCtx.window);
const ISO = isoCtx.window.ISO_CODES;

function loadPopulation() {
  const rows = parseCsv(fs.readFileSync(path.join(RAW, "wdi_population.csv"), "utf8").replace(/^\uFEFF/, ""));
  const head = rows[0], col = y => head.findIndex(h => h.startsWith(`${y} [YR${y}]`)), pop = {};
  for (const r of rows.slice(1)) {
    if (r[1] !== "SP.POP.TOTL") continue;
    const a2 = ISO.alpha2(r[3]);
    if (!a2) throw new Error(`Unknown country code in population file: ${r[3]}`);
    pop[a2] = YEARS.map(y => { const v = r[col(y)]; return v && v !== ".." ? +v : null; });
  }
  return pop;
}

function loadTrade() {   // JSON-stat 2.0 -> {reporter: {measure: {Exports, Imports}}}
  const d = JSON.parse(fs.readFileSync(path.join(RAW, "eu_trade_totals.json"), "utf8"));
  const cat = Object.fromEntries(d.id.map(k => [k, d.dimension[k].category.index]));
  const at = sel => { let i = 0; d.id.forEach((k, j) => { i = i * d.size[j] + cat[k][sel[k]]; }); return d.value[String(i)]; };
  const out = {}, labels = d.dimension.reporter.category.label;
  for (const rep of Object.keys(cat.reporter)) {
    const get = (flow, ind, div) => YEARS.map(y => { const v = at({ freq: "A", reporter: rep, partner: "WORLD", product: "TOTAL", flow, indicators: ind, time: String(y) }); return v == null ? null : v / div; });
    out[rep] = {
      label: labels[rep],
      value: { Imports: get("1", "VALUE_IN_EUROS", 1e6), Exports: get("2", "VALUE_IN_EUROS", 1e6) },             // million EUR
      quantity: { Imports: get("1", "QUANTITY_IN_100KG", 1e4), Exports: get("2", "QUANTITY_IN_100KG", 1e4) },   // thousand tonnes
    };
  }
  return out;
}

// Group membership by year (from the reporter labels in Comext; a country counts from the year it joined)
const EU27 = "AT BE BG CY CZ DE DK EE ES FI FR GR HR HU IE IT LT LU LV MT NL PL PT RO SE SI SK".split(" ");
const EA21 = "AT BE BG CY DE EE ES FI FR GR HR IE IT LT LU LV MT NL PT SI SK".split(" ");
const EA_JOIN = { AT: 1999, BE: 1999, DE: 1999, ES: 1999, FI: 1999, FR: 1999, IE: 1999, IT: 1999, LU: 1999, NL: 1999, PT: 1999,
  GR: 2001, SI: 2007, CY: 2008, MT: 2008, SK: 2009, EE: 2011, LV: 2014, LT: 2015, HR: 2023, BG: 2026 };
const EU_JOIN = { BE: 1958, DE: 1958, FR: 1958, IT: 1958, LU: 1958, NL: 1958, DK: 1973, IE: 1973, GB: 1973, GR: 1981, ES: 1986, PT: 1986,
  AT: 1995, FI: 1995, SE: 1995, CY: 2004, CZ: 2004, EE: 2004, HU: 2004, LT: 2004, LV: 2004, MT: 2004, PL: 2004, SI: 2004, SK: 2004,
  BG: 2007, RO: 2007, HR: 2013 };
const GROUPS = {
  EU27_2020: { name: "EU27 (2020 composition)", members: () => EU27 },
  EU: { name: "European Union (members at the time)", members: y => Object.keys(EU_JOIN).filter(c => EU_JOIN[c] <= y && !(c === "GB" && y >= 2020)) },
  EA21: { name: "Euro area (21 countries)", members: () => EA21 },
  EA: { name: "Euro area (members at the time)", members: y => Object.keys(EA_JOIN).filter(c => EA_JOIN[c] <= y) },
};

function buildComparison() {
  const pop = loadPopulation(), trade = loadTrade(), series = {}, names = {}, groups = {};
  for (const [rep, t] of Object.entries(trade)) {
    if (GROUPS[rep]) continue;
    if (!pop[rep]) throw new Error(`No population for reporter ${rep}`);
    series[rep] = { value: t.value, quantity: t.quantity, pop: pop[rep] };
    names[rep] = t.label.replace(/\s*\(.*\)$/, "");
  }
  for (const [code, g] of Object.entries(GROUPS)) {
    const sum = (pick) => YEARS.map((y, i) => {   // only when every member has a figure that year
      const vals = g.members(y).map(c => series[c] ? pick(series[c])[i] : null);
      return vals.some(v => v == null) ? null : vals.reduce((a, b) => a + b, 0);
    });
    series[code] = {
      value: { Imports: sum(s => s.value.Imports), Exports: sum(s => s.value.Exports) },
      quantity: { Imports: sum(s => s.quantity.Imports), Exports: sum(s => s.quantity.Exports) },
      pop: sum(s => s.pop),
    };
    names[code] = g.name;
    groups[code] = { name: g.name, members: YEARS.map(y => g.members(y).length) };
  }
  // CSV of the result: import and export per inhabitant for every reporter and year
  const r2 = v => v == null ? "" : Math.round(v * 100) / 100;
  const lines = ["reporter,reporter_name,is_group,year,population,imports_eur,exports_eur,imports_eur_per_inhabitant,exports_eur_per_inhabitant,imports_tonnes_per_inhabitant,exports_tonnes_per_inhabitant"];
  for (const [c, s] of Object.entries(series)) YEARS.forEach((y, i) => {
    const p = s.pop[i], im = s.value.Imports[i], ex = s.value.Exports[i], iq = s.quantity.Imports[i], eq = s.quantity.Exports[i];
    if (im == null || ex == null || !p) return;
    lines.push([c, `"${names[c]}"`, !!groups[c], y, p, Math.round(im * 1e6), Math.round(ex * 1e6), r2(im * 1e6 / p), r2(ex * 1e6 / p),
      iq == null ? "" : r2(iq * 1000 / p), eq == null ? "" : r2(eq * 1000 / p)].join(","));
  });
  fs.writeFileSync(path.join(SRC, "trade_per_inhabitant.csv"), lines.join("\n") + "\n");
  return { years: YEARS, series, names, groups, reference: "EU27_2020", source: "Eurostat Comext DS-045409; World Bank WDI SP.POP.TOTL" };
}

// ---- core ----------------------------------------------------------------------------------
const D = read("app_data.json");
const productFiles = new Set(fs.readdirSync(path.join(SRC, "products")).map(f => path.basename(f, ".json")));
const core = {
  frames: D.frames,
  names: D.names,
  hs2: Object.fromEntries(Object.entries(D.hs2).map(([c, h]) => [c, { name: h.name, icon: h.icon, full: h.full }])),
  products: D.products.filter(p => p.code === "TOTAL" || productFiles.has(p.code)).map(p => ({ code: p.code, name: p.name })),
  total: slimSeries({ value: D.measures.value.total, quantity: D.measures.quantity.total }),
  countries: buildComparison(),
};
let size = write("core.js", "LUX", core);

// ---- partner breakdown and product trees --------------------------------------------------
const pp = read("partner_products.json");
const trees = {}, labels = {};
for (const f of fs.readdirSync(path.join(SRC, "partners")).filter(f => f.endsWith(".json")).sort()) {
  const d = read(path.join("partners", f)), src = d.labels || {};
  const cut = n => {
    if (n.c.length > 2 && src[n.c]) labels[n.c] = short(src[n.c]);
    return [n.c, n.v, (n.k || []).slice(0, KEEP_CHILDREN).map(cut)];
  };
  const m = {};
  for (const measure of ["value", "quantity"])
    for (const flow of ["Exports", "Imports"])
      m[`${measure}|${flow}`] = Object.fromEntries(((d[measure] || {})[flow]?.k || []).map(ch => [ch.c, cut(ch)]));
  trees[path.basename(f, ".json")] = { year: +d.year, m };
}
size += write("details.js", "LUX_DETAILS", { pp: pp.partners, ppYears: pp.years, trees, labels });

// ---- one file per HS2 chapter ---------------------------------------------------------------
let n = 0;
for (const code of [...productFiles].sort()) {
  const p = read(path.join("products", `${code}.json`));
  size += write(path.join("products", `${code}.js`), "LUX_PRODUCTS", slimSeries({ value: p.value, quantity: p.quantity }), code);
  n++;
}
console.log(`data/js: core.js, details.js and ${n} product files, ${(size / 1e6).toFixed(1)} MB in total`);
