/* World map: Luxembourg's top 5 partners over time, with a click-through to each country's goods.
   Reads the bundles written by scripts/build-data.mjs (window.LUX, window.LUX_DETAILS and, on demand,
   window.LUX_PRODUCTS[code]). Wrapped in a function so it can share the page with other views. */
(() => {
const WORLD_URL = "https://cdn.jsdelivr.net/npm/world-atlas@2.0.2/countries-50m.json";
const LUX = [6.13, 49.61];
const MON = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
const $ = id => document.getElementById(id);
const CORE = window.LUX, DET = window.LUX_DETAILS || {};

if (!CORE) {
  $("loading").textContent = "No data found: run `node scripts/build-data.mjs` to create data/js/.";
  return;
}
const DATA = {
  frames: CORE.frames, series: CORE.total, product: "all goods", names: CORE.names, hs2: CORE.hs2,
  pp: DET.pp || {}, ppYears: DET.ppYears || [], trees: DET.trees || {}, labels: DET.labels || {},
  init: { measure: "value", flow: "Imports" }, ids: {},
};
new Set([...Object.keys(CORE.names), ...Object.keys(DATA.pp)]).forEach(c => { const n = window.ISO_CODES.numeric(c); if (n) DATA.ids[c] = n; });
const mapActive = () => window.ActiveView === "map";   // set by assets/app.js

const S = { flow: DATA.init.flow, measure: DATA.init.measure, step: "Yearly", speed: 1, pos: 0, playing: false, auto: true, focusKey: "", sel: null, chap: null, trend: true, pie: null };
const FR = DATA.frames;
const ser = () => DATA.series[`${S.measure}|${S.flow}`];
const name = c => DATA.names[c] || c;
const rankVar = r => `var(--r${r})`;
function fmt(v) {   // value in million EUR, quantity in thousand tonnes
  if (v == null) return "–";
  if (S.measure === "value") return v >= 1000 ? `€${(v / 1000).toFixed(1)} bn` : v >= 100 ? `€${v.toFixed(0)} m` : v >= 1 ? `€${v.toFixed(1)} m` : `€${(v * 1000).toFixed(0)} k`;
  return v >= 1000 ? `${(v / 1000).toFixed(1)} Mt` : v >= 10 ? `${v.toFixed(0)} kt` : v >= 0.01 ? `${v.toFixed(2)} kt` : `${(v * 1000).toFixed(0)} t`;
}
const PP = DATA.pp || {}, HS2 = DATA.hs2 || {}, TREE = DATA.trees || {}, LABELS = DATA.labels || {};
const CODE_OF = new Map(Object.entries(DATA.ids).map(([c, id]) => [id, c]));
const esc = s => String(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
// Each frame is a 12-month total. Stepping by year shows calendar years (December frames) labelled by
// the year; stepping by month labels each frame by its last month.
const periodLabel = f => S.step === "Yearly" ? f.slice(0, 4) : `${MON[+f.slice(5) - 1]} ${f.slice(0, 4)}`;

/* ---------- frames for the chosen step ---------- */
let IDX = [];
function buildIdx() {
  const n = FR.length;
  IDX = FR.map((f, i) => i).filter(i => S.step === "Monthly" || FR[i].slice(5) === "12");
  if (S.step === "Monthly" && IDX[IDX.length - 1] !== n - 1) IDX.push(n - 1);   // yearly: complete calendar years only
  $("scrub").max = IDX.length - 1;
  $("t0").textContent = FR[IDX[0]].slice(0, 4); $("t1").textContent = periodLabel(FR[IDX[IDX.length - 1]]);
}
const frame = () => IDX[S.pos];

/* ---------- map ---------- */
const svg = d3.select("#map"), gZoom = svg.append("g"), gLand = gZoom.append("g"), gOver = svg.append("g"), gFlows = gOver.append("g"), gDet = gOver.append("g"), gLabels = gOver.append("g"), gLux = gOver.append("g");   // Luxembourg drawn last, on top
let W = 800, H = 500, projection, path, features = [], byId = new Map(), mainPart = new Map(), view = d3.zoomIdentity;
const zoom = d3.zoom().scaleExtent([1, 60])
  .on("start", ev => { if (ev.sourceEvent) { S.auto = false; $("fit").hidden = false; } })
  .on("zoom", ev => { view = ev.transform; gZoom.attr("transform", view); drawOverlay(); });
svg.call(zoom).on("dblclick.zoom", null);

function largestPolygon(f) {
  if (!f.geometry || f.geometry.type !== "MultiPolygon") return f;
  let best = null, area = -1;
  f.geometry.coordinates.forEach(c => { const g = { type: "Feature", geometry: { type: "Polygon", coordinates: c } }, a = d3.geoArea(g); if (a > area) { area = a; best = g; } });
  return best;
}
function resize() {
  const r = $("mapwrap").getBoundingClientRect(); W = Math.max(320, r.width); H = Math.max(360, r.height);
  svg.attr("viewBox", `0 0 ${W} ${H}`);
  projection = d3.geoNaturalEarth1().fitExtent([[10, 10], [W - 10, H - 10]], { type: "Sphere" });
  path = d3.geoPath(projection);
  gLand.selectAll("path").attr("d", path);
  zoom.extent([[0, 0], [W, H]]).translateExtent([[-W, -H], [2 * W, 2 * H]]);
}

/* ---------- current top 5 ---------- */
function current() {
  const s = ser(), i = frame(), rows = (s.frames[i] || []).filter(r => r[1] > 0), world = s.world[i];
  return { top: rows.slice(0, 5).map(([c, v, prev], k) => ({ c, v, prev, r: k + 1, id: DATA.ids[c] })), all: rows, world, i };
}
function anchorOf(d) {   // projected point inside the country's main landmass
  const f = byId.get(d.id); if (!f) return null;
  return path.centroid(mainPart.get(d.id));
}

function focus(cur, animate) {
  const pts = [projection(LUX)];
  cur.top.forEach(d => { const f = byId.get(d.id); if (f) { const b = path.bounds(mainPart.get(d.id)); pts.push(b[0], b[1]); } });
  const xs = pts.map(p => p[0]), ys = pts.map(p => p[1]);
  let [x0, x1, y0, y1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
  const padX = 120, padY = 70;   // room for labels around the edge
  const k = pts.length === 1 ? 4 : Math.max(1, Math.min(60, Math.min((W - 2 * padX) / Math.max(1, x1 - x0), (H - 2 * padY) / Math.max(1, y1 - y0))));
  const t = d3.zoomIdentity.translate(W / 2, H / 2).scale(k).translate(-(x0 + x1) / 2, -(y0 + y1) / 2);
  const dur = animate ? Math.min(1100, 900 / S.speed + 200) : 0;
  svg.transition().duration(dur).ease(d3.easeCubicInOut).call(zoom.transform, t);
}

function focusCountry(code, animate) {
  const id = DATA.ids[code], f = id && mainPart.get(id); if (!f) return;
  const [[x0, y0], [x1, y1]] = path.bounds(f), pad = 90;
  const k = Math.max(1, Math.min(40, Math.min((W - 2 * pad) / Math.max(1, x1 - x0), (H - 2 * pad) / Math.max(1, y1 - y0))));
  const t = d3.zoomIdentity.translate(W / 2, H / 2).scale(k).translate(-(x0 + x1) / 2, -(y0 + y1) / 2);
  svg.transition().duration(animate ? 900 : 0).ease(d3.easeCubicInOut).call(zoom.transform, t);
}

function drawLand(cur) {
  const rank = new Map(cur.top.filter(d => d.id).map(d => [d.id, d.r]));
  const selId = S.sel && DATA.ids[S.sel];
  gLand.selectAll("path").attr("class", f => "country" + (f.id === selId ? " sel" : rank.has(f.id) ? " r" + rank.get(f.id) : f.id === "442" ? " lux" : ""));
  svg.classed("detail-mode", !!S.sel);
}

let CUR = null;
const curve = (p, q) => { const mx = (p[0] + q[0]) / 2, my = (p[1] + q[1]) / 2, dx = q[0] - p[0], dy = q[1] - p[1], len = Math.hypot(dx, dy) || 1, bend = Math.min(80, len * .22);
  return `M${p[0]},${p[1]} Q${mx - dy / len * bend},${my + dx / len * bend} ${q[0]},${q[1]}`; };
// Luxembourg: a flag on a pole planted at the capital, with a pulsing ring at its foot
const LU_FLAG = ["#ef3340", "#ffffff", "#00a3e0"];   // red, white, light blue
function drawLux(lux) {
  const lx = gLux.selectAll("g.luxpin").data([0]).join(enter => {
    const g = enter.append("g").attr("class", "luxpin");
    g.append("circle").attr("class", "luxring").attr("r", 9);
    g.append("line").attr("class", "luxpole").attr("x1", 0).attr("y1", 0).attr("x2", 0).attr("y2", -36);
    const flag = g.append("g").attr("transform", "translate(0.8,-36)").append("g").attr("class", "luxflag");
    LU_FLAG.forEach((c, k) => flag.append("rect").attr("y", k * 6).attr("width", 27).attr("height", 6).attr("fill", c));
    flag.append("rect").attr("class", "luxflag-edge").attr("width", 27).attr("height", 18);
    g.append("circle").attr("class", "luxdot").attr("r", 4);
    g.append("text").attr("class", "luxlbl").attr("x", 33).attr("y", -23).text("Luxembourg");
    g.append("title").text("Luxembourg");
    return g;
  });
  lx.attr("transform", `translate(${lux[0]},${lux[1]})`);
}
function drawDetailOverlay(lux) {
  gFlows.selectAll("g.flow").remove(); gLabels.selectAll("g.label").remove();
  drawLux(lux);
  const id = DATA.ids[S.sel], f = id && mainPart.get(id);
  if (!f || S.sel === "LU") { gDet.selectAll("*").remove(); return; }
  const a = view.apply(path.centroid(f)), yr = yearFor(frame()).yr;
  const tot = fl => { const e = PP[S.sel]?.[fl]?.[yr]; return e ? e[0][S.measure === "value" ? 0 : 1] : 0; };
  const ex = tot("Exports"), im = tot("Imports"), mx = Math.max(ex, im) || 1;
  const arcs = (S.flow === "Exports" ? [{ k: "exp", d: curve(lux, a), v: ex }] : [{ k: "imp", d: curve(a, lux), v: im }]).filter(r => r.v > 0);
  const g = gDet.selectAll("g.flow").data(arcs, r => r.k).join(enter => { const e = enter.append("g").attr("class", "flow"); e.append("path").attr("class", r => "flow-base " + r.k); e.append("path").attr("class", r => "flow-dash " + r.k); return e; });
  g.select(".flow-base").attr("d", r => r.d).attr("stroke-width", r => 2 + 7 * Math.sqrt(r.v / mx));
  g.select(".flow-dash").attr("d", r => r.d).attr("stroke-width", r => Math.max(2, (2 + 7 * Math.sqrt(r.v / mx)) * .6));
}
function drawOverlay() {
  if (!CUR || !path) return;
  const lux = view.apply(projection(LUX)), maxV = d3.max(CUR.top, d => d.v) || 1;
  if (S.sel) { drawDetailOverlay(lux); return; }
  gDet.selectAll("*").remove();
  const items = CUR.top.map(d => { const a = anchorOf(d); return a ? { ...d, a: view.apply(a) } : null; }).filter(Boolean);

  // flows: curved line Luxembourg <-> partner, width by amount
  const fl = gFlows.selectAll("g.flow").data(items, d => d.c);
  fl.exit().remove();
  const fe = fl.enter().append("g").attr("class", "flow");
  fe.append("path").attr("class", "flow-base"); fe.append("path").attr("class", "flow-dash");
  fe.merge(fl).each(function (d) {
    const w = 2 + 7 * Math.sqrt(d.v / maxV), g = d3.select(this);
    g.select(".flow-base").attr("d", curve(lux, d.a)).attr("stroke", rankVar(d.r)).attr("stroke-width", w);
    g.select(".flow-dash").attr("d", curve(lux, d.a)).attr("stroke", rankVar(d.r)).attr("stroke-width", Math.max(2, w * .6)).classed("in", S.flow === "Imports");
  });

  drawLux(lux);

  // labels: pushed away from Luxembourg, then separated so they never overlap
  const boxes = items.map(d => {
    let dx = d.a[0] - lux[0], dy = d.a[1] - lux[1]; const len = Math.hypot(dx, dy);
    if (len < 1) { dx = 0; dy = -1; } else { dx /= len; dy /= len; }
    const w = Math.max(name(d.c).length, fmt(d.v).length + 2) * 7.4 + 44, h = 40;
    return { d, w, h, x: d.a[0] + dx * 46 - w / 2, y: d.a[1] + dy * 40 - h / 2 };
  });
  // Luxembourg's own marker and name are a fixed obstacle the cards move around
  const all = [...boxes, { fixed: true, x: lux[0] - 10, y: lux[1] - 42, w: 112, h: 52 }];
  for (let it = 0; it < 80; it++) {
    let moved = false;
    for (let i = 0; i < all.length; i++) for (let j = i + 1; j < all.length; j++) {
      const a = all[i], b = all[j], ox = Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x) + 6, oy = Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y) + 6;
      if (ox <= 0 || oy <= 0) continue;
      moved = true;
      const s = (a.y + a.h / 2 < b.y + b.h / 2) ? -1 : 1;
      if (a.fixed) b.y -= s * oy; else if (b.fixed) a.y += s * oy; else { a.y += s * oy / 2; b.y -= s * oy / 2; }
    }
    boxes.forEach(b => { b.x = Math.max(6, Math.min(W - b.w - 6, b.x)); b.y = Math.max(6, Math.min(H - b.h - 6, b.y)); });
    if (!moved) break;
  }
  const lb = gLabels.selectAll("g.label").data(boxes, b => b.d.c);
  lb.exit().remove();
  const le = lb.enter().append("g").attr("class", "label");
  le.append("line").attr("class", "leader"); le.append("circle").attr("class", "anchor").attr("r", 3.5);
  const card = le.append("g").attr("class", "card");
  card.append("rect").attr("rx", 9); card.append("circle").attr("class", "badge").attr("r", 11).attr("cx", 18).attr("cy", 20);
  card.append("text").attr("class", "badge-t").attr("x", 18).attr("y", 24).attr("text-anchor", "middle");
  card.append("text").attr("class", "nm").attr("x", 36).attr("y", 17); card.append("text").attr("class", "val").attr("x", 36).attr("y", 32);
  le.merge(lb).each(function (b) {
    const g = d3.select(this), cx = b.x + b.w / 2, cy = b.y + b.h / 2;
    g.select(".leader").attr("x1", b.d.a[0]).attr("y1", b.d.a[1]).attr("x2", cx).attr("y2", cy);
    g.select(".anchor").attr("cx", b.d.a[0]).attr("cy", b.d.a[1]).attr("fill", rankVar(b.d.r));
    const c = g.select(".card").attr("transform", `translate(${b.x},${b.y})`);
    c.select("rect").attr("width", b.w).attr("height", b.h);
    c.select(".badge").attr("fill", rankVar(b.d.r)); c.select(".badge-t").text(b.d.r);
    c.select(".nm").text(name(b.d.c)); c.select(".val").text(fmt(b.d.v));
  });
}

/* ---------- side panel ---------- */
const ROW = 66;
function drawMorePartners(cur) {
  const el = $("morep"), extra = cur.all.slice(5, 10), open = OPEN.has("partners");
  if (!extra.length) { el.innerHTML = ""; return; }
  const hv = d3.sum(extra, r => r[1]);
  el.innerHTML = (open ? `<ol start="6">${extra.map(([c, v], j) => `<li class="click" role="button" tabindex="0" data-code="${c}"><span class="rk">${j + 6}</span><span class="gn">${esc(name(c))}</span><span class="gv">${fmt(v)} <small style="color:var(--muted);font-weight:400">${cur.world ? (v / cur.world * 100).toFixed(1) + "%" : ""}</small></span></li>`).join("")}</ol>` : "") +
    `<button class="more" data-key="partners" aria-expanded="${open}">${open ? "Show top 5 only" : `⋯ Ranks 6–${5 + extra.length} · ${fmt(hv)}${cur.world ? ` (${(hv / cur.world * 100).toFixed(0)}%)` : ""}`}</button>`;
  wireMore(el, () => drawMorePartners(CUR));
  el.querySelectorAll("li.click").forEach(li => { li.onclick = () => select(li.dataset.code); li.onkeydown = e => { if (e.key === "Enter") select(li.dataset.code); }; });
}
function drawPanel(cur) {
  drawMorePartners(cur);
  const s = ser(), share = cur.world ? d3.sum(cur.top, d => d.v) / cur.world : null;
  $("kpi-k").textContent = `Top 5 share of ${S.flow.toLowerCase()}`;
  $("kpi-v").textContent = share == null ? "–" : `${(share * 100).toFixed(0)}%`;
  $("kpi-n").textContent = `of ${fmt(cur.world)} in total · ${periodLabel(FR[cur.i])}`;
  const rows = d3.select("#list").selectAll("div.row").data(cur.top, d => d.c);
  rows.exit().style("opacity", 0).transition().duration(300).remove();
  const en = rows.enter().append("div").attr("class", "row").style("opacity", 0).style("transform", d => `translateY(${(d.r - 1) * ROW + 20}px)`);
  en.append("div").attr("class", "badge"); en.append("div").attr("class", "nm"); en.append("div").attr("class", "val");
  en.append("div").attr("class", "bar").append("i"); en.append("div").attr("class", "chg");
  en.attr("role", "button").attr("tabindex", 0).on("click", (ev, d) => select(d.c)).on("keydown", (ev, d) => { if (ev.key === "Enter") select(d.c); });
  en.merge(rows).each(function (d) {
    const r = d3.select(this);
    r.style("opacity", 1).style("transform", `translateY(${(d.r - 1) * ROW}px)`);
    r.select(".badge").style("background", rankVar(d.r)).text(d.r);
    r.select(".nm").text(name(d.c)).attr("title", name(d.c));
    r.select(".val").text(fmt(d.v));
    r.select(".bar i").style("width", cur.world ? `${Math.min(100, d.v / cur.world * 100)}%` : "0").style("background", rankVar(d.r));
    const chg = !d.prev ? ["new", "up", "New in top 25"] : d.prev === d.r ? ["=", "", "Same rank as a year earlier"] : d.prev > d.r ? [`▲ ${d.prev - d.r}`, "up", `Up from #${d.prev} a year earlier`] : [`▼ ${d.r - d.prev}`, "down", `Down from #${d.prev} a year earlier`];
    r.select(".chg").attr("class", "chg " + chg[1]).attr("title", chg[2]).text(`${cur.world ? (d.v / cur.world * 100).toFixed(1) + "% · " : ""}${chg[0]}`);
  });
}

/* ---------- country detail ---------- */
function yearFor(i) {   // the calendar year shown for a 12-month frame: that year if the frame ends in December, else the year before
  const f = FR[i], y = +f.slice(0, 4), m = +f.slice(5), ys = DATA.ppYears || [y];
  const yr = Math.max(ys[0], Math.min(ys[ys.length - 1], m === 12 ? y : y - 1));
  return { yr, partial: m !== 12 || yr !== y };
}
function rankIn(flow, code, i) {
  const fr = DATA.series[`${S.measure}|${flow}`].frames[i] || [], k = fr.findIndex(r => r[0] === code);
  return k >= 0 ? k + 1 : null;
}
// Ranked lists show the top 5; the rest sits behind a "⋯" button (open state kept per list).
const OPEN = new Set();
function rankedList(key, rows, total, col, rowHtml, noun) {
  const first = rows.slice(0, 5), more = rows.slice(5), open = OPEN.has(key), max = rows.length ? rows[0].v : 1;
  const li = (r, j) => rowHtml(r, j, max);
  const listed = d3.sum(rows, r => r.v), rest = total - listed, hiddenV = d3.sum(more, r => r.v);
  return `<ol>${first.map(li).join("")}</ol>` +
    (more.length ? (open ? `<ol>${more.map((r, j) => li(r, j + 5)).join("")}</ol>` : "") +
      `<button class="more" data-key="${esc(key)}" aria-expanded="${open}">${open ? "Show top 5 only" : `⋯ ${more.length} more ${more.length === 1 ? { categories: "category", items: "item" }[noun] || noun : noun}${total ? ` · ${fmt(hiddenV)} (${(hiddenV / total * 100).toFixed(0)}%)` : ""}`}</button>` : "") +
    ((open || !more.length) && rest > total * 0.005 ? `<div class="other">Not itemised: ${fmt(rest)} (${(rest / total * 100).toFixed(0)}%)</div>` : "");
}
function wireMore(root, redraw) {
  root.querySelectorAll("button.more").forEach(b => b.onclick = () => { const k = b.dataset.key; OPEN.has(k) ? OPEN.delete(k) : OPEN.add(k); redraw(); });
}

function goodsList(code, flow, yr) {
  const e = PP[code]?.[flow]?.[yr];
  if (!e) return `<p class="empty">No ${flow === "Exports" ? "exports" : "imports"} recorded in ${yr}.</p>`;
  const k = S.measure === "value" ? 1 : 2, total = e[0][k - 1];
  const rows = e[1].map(r => ({ c: r[0], v: r[k] })).filter(r => r.v > 0).sort((a, b) => b.v - a.v);
  if (!rows.length || !total) return `<p class="empty">Nothing recorded by ${S.measure === "value" ? "value" : "weight"} in ${yr}.</p>`;
  const col = flow === "Exports" ? "var(--exp)" : "var(--imp)", can = true;
  return rankedList(`${code}|${flow}|chapters`, rows, total, col, (r, j, max) => { const h = HS2[r.c] || {};
    return `<li title="${esc(h.full || h.name || r.c)}"${can ? ` class="click" role="button" tabindex="0" data-flow="${flow}" data-chap="${r.c}"` : ""}><span class="rk">${j + 1}</span><span class="gn"><small>${r.c}</small>${h.icon ? h.icon + " " : ""}${esc(h.name || "Chapter " + r.c)}</span><span class="gv">${fmt(r.v)} <small style="color:var(--muted);font-weight:400">${(r.v / total * 100).toFixed(0)}%</small></span><span class="gb"><i style="width:${(r.v / max * 100).toFixed(1)}%;background:${col}"></i></span></li>`; }, "categories");
}
// Customs code levels in plain words: 2 digits = broad category (HS chapter), 4 = product group
// (HS heading), 6 = product type (HS subheading), 8 = specific product (EU CN code).
const LEVEL = { 2: "Category", 4: "Product group", 6: "Product type", 8: "Specific product" };
const LEVELS = { 2: "Categories", 4: "Product groups", 6: "Product types", 8: "Specific products" };
const LEVEL_HELP = "Customs codes get more specific with each pair of digits: category (2 digits) › product group (4) › product type (6) › specific product (8).";
function labelOf(code) {
  if (code.length === 2) { const h = HS2[code] || {}; return (h.icon ? h.icon + " " : "") + (h.name || "Chapter " + code); }
  return LABELS[code] || code;
}
function nodeAt(T, flow, path) {   // node = [code, amount, children]
  let n = T.m[`${S.measure}|${flow}`][path[0]];
  for (const c of path.slice(1)) { if (!n) return null; n = n[2].find(k => k[0] === c); }
  return n || null;
}
function goUp() { S.chap.path.pop(); if (!S.chap.path.length) S.chap = null; drawDetail(CUR); }
function drawChapter(cur) {
  const c = S.sel, { flow, path } = S.chap, T = TREE[c], el = $("detail"), nm = name(c), code = path[path.length - 1];
  const node = T && nodeAt(T, flow, path), h = HS2[path[0]] || {};
  const col = flow === "Exports" ? "var(--exp)" : "var(--imp)", dir = flow === "Exports" ? `Luxembourg exports to ${nm}` : `Luxembourg imports from ${nm}`;
  const crumbs = [`<button class="crumb" data-depth="0">${esc(nm)}</button>`, ...path.map((p, k) =>
    k === path.length - 1 ? `<span class="crumb now">${p.length === 2 ? esc(labelOf(p)) : p}</span>` : `<button class="crumb" data-depth="${k + 1}">${p.length === 2 ? esc(labelOf(p)) : p}</button>`)].join('<span class="sep">›</span>');
  let body;
  if (!node) body = `<p class="empty">Nothing recorded ${S.measure === "value" ? "by value" : "by weight"} for this item in ${T ? T.year : "the detailed data"}.</p>`;
  else {
    const [, total, kids] = node;
    const rows = kids.map(([c, v, sub]) => ({ c, v, sub })).filter(r => r.v > 0);
    body = `<div class="dk"><div class="wide"><div class="k">${esc(dir)} · ${T.year}</div><div class="v">${fmt(total)}</div>${code.length === 2 ? `<div class="n">${esc(h.full || h.name || "")}</div>` : ""}</div></div>` +
      (rows.length ? `<section class="goods"><h3><i style="background:${col}"></i>${LEVELS[kids[0][0].length]}</h3>${rankedList(`${c}|${flow}|${path.join(">")}`, rows, total, col, (r, j, max) =>
        `<li class="prod click${r.sub.length ? "" : " leaf-item"}" role="button" tabindex="0" data-code="${r.c}" title="${esc(LABELS[r.c] || r.c)}"><span class="rk">${j + 1}</span><span class="gn"><small>${r.c}</small>${esc(LABELS[r.c] || "Code " + r.c)}</span><span class="gv">${fmt(r.v)} <small style="color:var(--muted);font-weight:400">${total ? (r.v / total * 100).toFixed(0) : 0}%</small></span><span class="gb"><i style="width:${(r.v / max * 100).toFixed(1)}%;background:${col}"></i></span>${r.sub.length ? `<span class="leaf">Mainly ${r.sub[0][0]} · ${esc(LABELS[r.sub[0][0]] || "")}</span>` : ""}</li>`, "items")}</section>`
        : `<p class="empty">This is the most detailed level available: a specific product (8-digit code).</p>`);
  }
  const yr = yearFor(cur.i).yr;
  el.innerHTML = `<button class="back" id="back">← Back</button>
    <nav class="crumbs" aria-label="Product path">${crumbs}</nav>
    <div><h2${code.length > 2 ? ` class="long" title="${esc(LABELS[code] || code)}"` : ""}>${code.length === 2 ? esc(labelOf(code)) : esc(LABELS[code] || code)}</h2><div class="sub" title="${LEVEL_HELP}">${LEVEL[code.length]} · code ${code} · ${flow === "Exports" ? "exports to" : "imports from"} ${esc(nm)} · ${S.measure === "value" ? "by value" : "by weight"}</div></div>
    ${body}
    ${T && T.year !== yr ? `<p class="note">Product detail is for ${T.year}, the most detailed year prepared; the map shows ${yr}.</p>` : ""}`;
  $("back").onclick = goUp;
  wireMore(el, () => drawDetail(CUR));
  el.querySelectorAll(".crumb[data-depth]").forEach(b => b.onclick = () => { const k = +b.dataset.depth; if (k === 0) S.chap = null; else S.chap.path = path.slice(0, k); drawDetail(CUR); });
  el.querySelectorAll("li.click").forEach(li => {
    const open = () => { S.chap.path.push(li.dataset.code); drawDetail(CUR); el.scrollTop = 0; };
    li.onclick = open; li.onkeydown = e => { if (e.key === "Enter") open(); };
  });
}
function drawDetail(cur) {
  queueMicrotask(() => drawPie(false));   // the partner chart follows every move in the product drill-down
  if (S.chap) { drawChapter(cur); return; }
  const c = S.sel, { yr, partial } = yearFor(cur.i), el = $("detail");
  const tot = fl => { const e = PP[c]?.[fl]?.[yr]; return e ? e[0][S.measure === "value" ? 0 : 1] : 0; };
  const ex = tot("Exports"), im = tot("Imports"), rx = rankIn("Exports", c, cur.i), ri = rankIn("Imports", c, cur.i);
  const nm = name(c), by = S.measure === "value" ? "by value" : "by weight";
  el.innerHTML = c === "LU" ? `<button class="back" id="back">← Top 5</button><h2>Luxembourg</h2><p class="empty">This is the reporter. Pick a partner country on the map.</p>` :
    `<div class="detail-actions"><button class="back" id="back">← Top 5</button>${S.trend ? "" : `<button class="back" id="trend-open">📈 Trend over time</button>`}</div>
    <div><h2>${esc(nm)}</h2><div class="sub">Calendar year ${yr}${partial ? " (latest full year)" : ""} · ${by} · all goods</div></div>
    <div class="dk">
      <div><div class="k">Imports from ${esc(nm)}</div><div class="v">${fmt(im)}</div><div class="n">${ri ? `#${ri} supplier, ${periodLabel(FR[cur.i])}` : "&nbsp;"}</div></div>
      <div><div class="k">Exports to ${esc(nm)}</div><div class="v">${fmt(ex)}</div><div class="n">${rx ? `#${rx} market, ${periodLabel(FR[cur.i])}` : "&nbsp;"}</div></div>
      ${S.measure === "value" ? `<div class="wide"><div class="k">Trade balance</div><div class="v" style="color:${ex - im >= 0 ? "var(--up)" : "var(--down)"}">${ex - im >= 0 ? "+" : "−"}${fmt(Math.abs(ex - im))}</div><div class="n">${ex - im >= 0 ? "Luxembourg sells more than it buys" : "Luxembourg buys more than it sells"}</div></div>` : ""}
    </div>
    ${S.flow === "Imports"
      ? `<section class="goods"><h3><i style="background:var(--imp)"></i>Luxembourg imports from ${esc(nm)}</h3>${goodsList(c, "Imports", yr)}</section>`
      : `<section class="goods"><h3><i style="background:var(--exp)"></i>Luxembourg exports to ${esc(nm)}</h3>${goodsList(c, "Exports", yr)}</section>`}
    ${TREE[c] ? `<p class="note">Click a category to see its product groups (keep clicking for product types and specific products), and, below the map, the countries Luxembourg ${S.flow === "Exports" ? "exports it to" : "imports it from"}.</p>` : `<p class="note">Click a category to see, below the map, the countries Luxembourg ${S.flow === "Exports" ? "exports it to" : "imports it from"}. Product detail is prepared for the 40 largest partners only.</p>`}`;
  $("back").onclick = () => select(null);
  if ($("trend-open")) $("trend-open").onclick = () => { S.trend = true; drawDetail(CUR); drawTrend(); };
  wireMore(el, () => drawDetail(CUR));
  el.querySelectorAll("li.click").forEach(li => {
    const open = () => {
      S.pie = li.dataset.chap;
      if (TREE[c]) { S.chap = { flow: li.dataset.flow, path: [li.dataset.chap] }; drawDetail(CUR); el.scrollTop = 0; }
      drawPie(true);
    };
    li.onclick = open; li.onkeydown = e => { if (e.key === "Enter") open(); };
  });
}
/* ---------- trend popup: the selected flow with the selected country, per calendar year ---------- */
function drawTrend() {
  const box = $("trend"), c = S.sel;
  const years = DATA.ppYears, k = S.measure === "value" ? 0 : 1;
  const pts = c && c !== "LU" ? years.map(y => { const e = PP[c]?.[S.flow]?.[y]; return { y, v: e ? e[0][k] : 0 }; }) : [];
  if (!S.trend || !pts.some(p => p.v > 0)) { box.hidden = true; return; }
  box.hidden = false;
  const nm = name(c), col = S.flow === "Exports" ? "var(--exp)" : "var(--imp)";
  $("trend-title").textContent = S.flow === "Exports" ? `Exports to ${nm}` : `Imports from ${nm}`;
  $("trend-sub").textContent = `Per calendar year, ${S.measure === "value" ? "value in €" : "weight in tonnes"} · all goods`;
  const el = $("trend-chart"), w = el.clientWidth || 340, h = 150, m = { t: 12, r: 14, b: 22, l: 50 };
  const x = d3.scaleLinear(d3.extent(pts, p => p.y), [m.l, w - m.r]);
  const y = d3.scaleLinear([0, d3.max(pts, p => p.v) * 1.08 || 1], [h - m.b, m.t]).nice(4);
  const svgT = d3.select(el).attr("viewBox", `0 0 ${w} ${h}`);
  svgT.selectAll("*").remove();
  y.ticks(4).forEach(t => {
    svgT.append("line").attr("class", "trend-grid").attr("x1", m.l).attr("x2", w - m.r).attr("y1", y(t)).attr("y2", y(t));
    svgT.append("text").attr("class", "trend-tick").attr("x", m.l - 6).attr("y", y(t) + 3.5).attr("text-anchor", "end").text(t === 0 ? "0" : fmt(t));
  });
  x.ticks(5).filter(t => Number.isInteger(t)).forEach(t => svgT.append("text").attr("class", "trend-tick").attr("x", x(t)).attr("y", h - 6).attr("text-anchor", "middle").text(t));
  svgT.append("path").attr("d", d3.area().x(p => x(p.y)).y0(y(0)).y1(p => y(p.v)).curve(d3.curveMonotoneX)(pts)).attr("fill", col).attr("opacity", .14);
  svgT.append("path").attr("d", d3.line().x(p => x(p.y)).y(p => y(p.v)).curve(d3.curveMonotoneX)(pts)).attr("fill", "none").attr("stroke", col).attr("stroke-width", 2.2);
  // the year the map is showing
  const cy = yearFor(frame()).yr, cp = pts.find(p => p.y === cy);
  if (cp) {
    svgT.append("line").attr("class", "trend-now").attr("x1", x(cy)).attr("x2", x(cy)).attr("y1", m.t).attr("y2", h - m.b);
    svgT.append("circle").attr("cx", x(cy)).attr("cy", y(cp.v)).attr("r", 4.5).attr("fill", col).attr("stroke", "var(--surface)").attr("stroke-width", 2);
  }
  // hover readout; click jumps the map to that year
  const hov = svgT.append("g").attr("class", "trend-hover").style("display", "none");
  hov.append("line").attr("y1", m.t).attr("y2", h - m.b);
  hov.append("circle").attr("r", 3.5).attr("fill", col);
  const lab = hov.append("text").attr("y", m.t + 8);
  const near = ev => { const yr = Math.round(x.invert(d3.pointer(ev)[0])); return pts.find(p => p.y === Math.max(years[0], Math.min(years[years.length - 1], yr))); };
  svgT.append("rect").attr("x", m.l).attr("y", m.t).attr("width", w - m.l - m.r).attr("height", h - m.t - m.b).attr("fill", "transparent").style("cursor", "pointer")
    .on("pointermove", ev => { const p = near(ev); hov.style("display", null); hov.select("line").attr("x1", x(p.y)).attr("x2", x(p.y)); hov.select("circle").attr("cx", x(p.y)).attr("cy", y(p.v));
      lab.text(`${p.y}: ${fmt(p.v)}`).attr("x", x(p.y) > w * .6 ? x(p.y) - 6 : x(p.y) + 6).attr("text-anchor", x(p.y) > w * .6 ? "end" : "start"); })
    .on("pointerleave", () => hov.style("display", "none"))
    .on("click", ev => { const p = near(ev), k2 = IDX.findIndex(i => FR[i] === `${p.y}-12`); if (k2 >= 0) { stop(); S.pos = k2; update(true); } });
  // summary: latest year, change over the period and peak
  const last = pts[pts.length - 1], first = pts.find(p => p.v > 0), peak = pts.reduce((a, b) => (b.v > a.v ? b : a));
  const chg = first && first.v ? (last.v / first.v - 1) * 100 : null;
  $("trend-foot").innerHTML = `<b>${fmt(last.v)}</b> in ${last.y}` + (chg == null ? "" : ` · <span class="${chg >= 0 ? "up" : "down"}">${chg >= 0 ? "+" : "−"}${Math.abs(chg).toFixed(0)}%</span> since ${first.y}`) + ` · peak ${fmt(peak.v)} in ${peak.y}` +
    `<span class="trend-hint">Click the chart to jump to a year</span>`;
}
$("trend-close").onclick = () => { S.trend = false; drawTrend(); if (S.sel) drawDetail(CUR); };

function select(code) {
  S.sel = code && code === S.sel ? null : code; S.chap = null; S.trend = true; if (!S.sel) S.pie = null;
  const on = !!S.sel;
  $("detail").hidden = !on; $("topkpi").hidden = on; $("list").hidden = on; $("morep").hidden = on;
  document.querySelector(".main").classList.toggle("wide", on);
  S.focusKey = ""; S.auto = true; $("fit").hidden = true;
  update(true);
}

/* ---------- timeline sparkline ---------- */
function drawSpark() {
  const el = $("spark"), w = el.clientWidth || 600, h = 34, s = ser();
  const xs = IDX.map(i => s.world[i] || 0), x = d3.scaleLinear([0, IDX.length - 1], [7, w - 7]), y = d3.scaleLinear([0, d3.max(xs) || 1], [h - 2, 3]);
  const t5 = IDX.map(i => d3.sum((s.frames[i] || []).slice(0, 5), r => r[1]));
  const sp = d3.select(el).attr("viewBox", `0 0 ${w} ${h}`);
  sp.selectAll("*").remove();
  sp.append("path").attr("d", d3.area().x((d, k) => x(k)).y0(h - 2).y1(d => y(d))(xs)).attr("fill", "var(--line)");
  sp.append("path").attr("d", d3.area().x((d, k) => x(k)).y0(h - 2).y1(d => y(d))(t5)).attr("fill", "var(--r4)").attr("opacity", .55);
  sp.append("line").attr("id", "cur").attr("y1", 0).attr("y2", h).attr("stroke", "var(--fg)").attr("stroke-width", 1.5);
  sp.append("line").attr("id", "spark-hover").attr("y1", 0).attr("y2", h).attr("stroke", "var(--fg-2)").attr("stroke-dasharray", "2 2").style("display", "none");
  sp.on("click", ev => { const [mx] = d3.pointer(ev); stop(); S.pos = Math.round(x.invert(mx)); update(true); });
  el._x = x; el._xs = xs; el._t5 = t5;
}
// Month and year under the pointer when hovering the timeline (mini chart or slider)
(() => {
  const track = document.querySelector(".track"), tipEl = $("spark-tip");
  track.addEventListener("pointermove", ev => {
    const el = $("spark"), x = el._x; if (!x) return;
    const r = el.getBoundingClientRect(), mx = ev.clientX - r.left;
    const k = Math.max(0, Math.min(IDX.length - 1, Math.round(x.invert(mx))));
    d3.select("#spark-hover").style("display", null).attr("x1", x(k)).attr("x2", x(k));
    tipEl.textContent = periodLabel(FR[IDX[k]]);
    tipEl.hidden = false;
    const tw = tipEl.offsetWidth, tr = track.getBoundingClientRect();
    tipEl.style.left = Math.max(0, Math.min(tr.width - tw, (r.left - tr.left) + x(k) - tw / 2)) + "px";
  });
  track.addEventListener("pointerleave", () => { tipEl.hidden = true; d3.select("#spark-hover").style("display", "none"); });
})();
const moveSparkCursor = () => { const x = $("spark")._x; if (x) d3.select("#cur").attr("x1", x(S.pos)).attr("x2", x(S.pos)); };

/* ---------- update ---------- */
function update(animate) {
  const cur = current(); CUR = cur;
  document.documentElement.dataset.flow = S.flow;
  $("title").textContent = S.flow === "Exports" ? "Who buys the most from Luxembourg?" : "Where does Luxembourg buy the most from?";
  $("period").textContent = periodLabel(FR[cur.i]);
  $("scrub").value = S.pos; moveSparkCursor();
  drawLand(cur);
  if (S.sel) drawDetail(cur); else drawPanel(cur);
  const key = S.sel ? "sel:" + S.sel : S.flow + S.measure + cur.top.map(d => d.c).sort().join();
  if (S.auto && key !== S.focusKey) { S.focusKey = key; S.sel ? focusCountry(S.sel, animate) : focus(cur, animate); } else drawOverlay();
  drawTrend(); drawPie(false);
  const hidden = cur.top.filter(d => !d.id).map(d => name(d.c));
  $("note").textContent = `${S.measure === "value" ? "Value" : "Weight"} of ${S.flow.toLowerCase()} ${S.step === "Yearly" ? "per calendar year" : "over the 12 months up to each month"}. Source: Eurostat Comext DS-045409.` +
    (hidden.length ? ` Not on the map: ${hidden.join(", ")}.` : "") + " Click a country for the goods traded with it; drag or scroll to explore.";
}

/* ---------- playback ---------- */
let timer = null;
const baseMs = () => ({ Yearly: 1500, Monthly: 320 }[S.step]) / S.speed;
function tick() { if (S.pos >= IDX.length - 1) { stop(); return; } S.pos++; update(true); timer = setTimeout(tick, baseMs()); }
function play() { if (S.pos >= IDX.length - 1) S.pos = 0; S.playing = true; $("play").setAttribute("aria-label", "Pause"); $("ico").innerHTML = '<path d="M6 4h4.5v16H6zM13.5 4H18v16h-4.5z"/>'; update(true); timer = setTimeout(tick, baseMs()); }
function stop() { S.playing = false; clearTimeout(timer); $("play").setAttribute("aria-label", "Play"); $("ico").innerHTML = '<path d="M7 4.5v15l13-7.5z"/>'; }

/* ---------- controls ---------- */
function seg(id, k) {
  const btns = document.querySelectorAll(`#${id} button`);
  btns.forEach(b => { b.setAttribute("aria-pressed", b.dataset.v === S[k]); b.onclick = () => { S[k] = b.dataset.v; if (S.chap && S.chap.flow !== S.flow) S.chap = null; btns.forEach(o => o.setAttribute("aria-pressed", o === b)); S.focusKey = ""; S.auto = true; $("fit").hidden = true; drawSpark(); update(true); }; });
}
seg("g-flow", "flow"); seg("g-measure", "measure");
$("play").onclick = () => S.playing ? stop() : play();
$("scrub").oninput = e => { stop(); S.pos = +e.target.value; update(true); };
$("speed").onchange = e => S.speed = +e.target.value;
$("step").onchange = e => { const f = frame(); S.step = e.target.value; buildIdx(); S.pos = IDX.findIndex(i => i >= f); if (S.pos < 0) S.pos = IDX.length - 1; drawSpark(); update(false); };
$("fit").onclick = () => { S.auto = true; S.focusKey = ""; $("fit").hidden = true; update(true); };
document.addEventListener("keydown", e => { if (!mapActive() || e.key !== "Escape" || !S.sel) return; if (S.chap) goUp(); else if (S.trend && !$("trend").hidden) { S.trend = false; drawTrend(); drawDetail(CUR); } else select(null); });
document.addEventListener("keydown", e => { if (!mapActive()) return; if (e.target.tagName === "INPUT" || e.target.tagName === "SELECT") return; if (e.code === "Space") { e.preventDefault(); S.playing ? stop() : play(); } if (e.code === "ArrowRight") { stop(); S.pos = Math.min(IDX.length - 1, S.pos + 1); update(true); } if (e.code === "ArrowLeft") { stop(); S.pos = Math.max(0, S.pos - 1); update(true); } });

// tooltip on any country
const tip = $("tip");
gLand.on("pointermove", ev => {
  const f = ev.target.__data__; if (!f) return;
  const code = CODE_OF.get(f.id);
  const rows = CUR.all, k = code ? rows.findIndex(r => r[0] === code) : -1;
  tip.innerHTML = k >= 0 ? `<b>#${k + 1} ${name(code)}</b><br>${fmt(rows[k][1])}${CUR.world ? ` · ${(rows[k][1] / CUR.world * 100).toFixed(1)}%` : ""}<br><span class="m">Click for details</span>` : `<b>${code ? name(code) : f.properties.name}</b><br><span class="m">${f.id === "442" ? "Reporter" : code ? "Outside the top 10 · click for details" : "No trade recorded"}</span>`;
  tip.hidden = false;
  const r = $("mapwrap").getBoundingClientRect(), x = ev.clientX - r.left, y = ev.clientY - r.top;
  tip.style.left = Math.min(r.width - tip.offsetWidth - 8, x + 14) + "px"; tip.style.top = Math.max(8, y - 40) + "px";
}).on("pointerleave", () => tip.hidden = true)
  .on("click", ev => { const f = ev.target.__data__; if (!f) return; select(CODE_OF.get(f.id) || null); });

/* ---------- partner pie: who Luxembourg trades the clicked category with, in % of the category ---------- */
// Categories (2 digits) use the bundled 12-month partner rankings. Deeper levels (product group,
// type, specific product) are loaded from Eurostat for the calendar year shown on the map, all partners.
const EUROSTAT = "https://ec.europa.eu/eurostat/api/comext/dissemination/statistics/1.0/data/DS-045409";
const liveCache = new Map();
function loadLive(code, flow, year) {   // -> {rows: [[partner, value, quantity]], world: [value, quantity]} in million € / thousand t
  const key = `${code}|${flow}|${year}`;
  if (!liveCache.has(key)) {
    const q = new URLSearchParams([["format", "JSON"], ["reporter", "LU"], ["product", code], ["freq", "A"], ["time", String(year)],
      ["flow", flow === "Imports" ? "1" : "2"], ["indicators", "VALUE_IN_EUROS"], ["indicators", "QUANTITY_IN_100KG"]]);
    liveCache.set(key, fetch(`${EUROSTAT}?${q}`).then(r => r.json()).then(d => {
      if (d.error) throw new Error("Eurostat returned no data for this product and year.");
      const cat = Object.fromEntries(d.id.map(k => [k, d.dimension[k].category.index])), byPos = {};
      Object.entries(cat.partner).forEach(([c, i]) => { byPos[i] = c; });
      const out = {}, strides = d.size.map((_, j) => d.size.slice(j + 1).reduce((a, b) => a * b, 1));
      const pj = d.id.indexOf("partner"), ij = d.id.indexOf("indicators");
      Object.entries(d.value).forEach(([k, v]) => {
        const n = +k, partner = byPos[Math.floor(n / strides[pj]) % d.size[pj]], ind = Object.keys(cat.indicators).find(x => cat.indicators[x] === Math.floor(n / strides[ij]) % d.size[ij]);
        (out[partner] = out[partner] || [0, 0])[ind === "VALUE_IN_EUROS" ? 0 : 1] = ind === "VALUE_IN_EUROS" ? v / 1e6 : v / 1e4;
      });
      return { world: out.WORLD || [0, 0], rows: Object.entries(out).filter(([c]) => /^[A-Z]{2}$/.test(c)).map(([c, [v, qn]]) => [c, v, qn]) };
    }).catch(err => { liveCache.delete(key); throw err; }));
  }
  return liveCache.get(key);
}
const pieName = c => /^Q[P-Z]$/.test(c) ? "Confidential or not specified" : name(c);
function pieCode() { return S.chap && S.chap.flow === S.flow ? S.chap.path[S.chap.path.length - 1] : S.pie; }

const PIE_COLOURS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6"], PIE_OTHER = "#c3c2b7";
function drawPie(reveal) {
  const box = $("pie"), code = pieCode();
  if (!code) { box.hidden = true; return; }
  const deep = code.length > 2, yr = yearFor(frame()).yr, k = S.measure === "value" ? 1 : 2, verb = S.flow === "Exports" ? "exports" : "imports";
  const what = code.length === 2 ? (HS2[code] ? HS2[code].name.toLowerCase() : "this category") : (LABELS[code] || `product ${code}`);
  box.hidden = false;
  $("pie-eyebrow").textContent = `${LEVEL[code.length]} ${code} · ${deep ? yr : periodLabel(FR[frame()])}`;
  $("pie-title").textContent = S.flow === "Exports" ? `Where Luxembourg exports it to` : `Where Luxembourg imports it from`;
  if (deep) { $("pie-sub").textContent = `${what} · loading from Eurostat…`; d3.select("#pie-chart").selectAll("*").remove(); $("pie-legend").innerHTML = ""; $("pie-note").textContent = ""; }
  const source = deep ? loadLive(code, S.flow, yr).then(d => ({ rows: d.rows.map(r => [r[0], r[k]]), total: d.world[k - 1] }))
    : loadProduct(code).then(series => { const s = series[`${S.measure}|${S.flow}`], i = frame(); return { rows: (s.frames[i] || []).map(r => [r[0], r[1]]), total: s.world[i] }; });
  source.then(({ rows, total }) => {
    if (pieCode() !== code) return;   // the user moved on meanwhile
    rows = rows.filter(r => r[1] > 0).sort((a, b) => b[1] - a[1]);
    $("pie-sub").textContent = `Share of each partner in Luxembourg's ${verb} of ${code.length === 2 ? (HS2[code] ? HS2[code].full : what) : what}, ${S.measure === "value" ? "by value" : "by weight"}. Total: ${fmt(total)}.`;
    if (!rows.length || !total) {
      d3.select("#pie-chart").selectAll("*").remove(); $("pie-legend").innerHTML = "";
      $("pie-note").textContent = `No ${verb} of this product recorded ${deep ? "in " + yr : "in this period"}${S.measure === "quantity" ? " by weight" : ""}.`; return;
    }
    // the 7 largest partners, the selected country if it is further down, and everyone else as "Other"
    const top = rows.slice(0, 7), sel = S.sel && !top.find(r => r[0] === S.sel) ? rows.find(r => r[0] === S.sel) : null;
    const shown = sel ? [...top, sel] : top, rest = total - d3.sum(shown, r => r[1]);
    const slices = shown.map(([c, v], j) => ({ c, v, label: pieName(c), col: j < 7 ? PIE_COLOURS[j] : PIE_COLOURS[6], rank: rows.findIndex(r => r[0] === c) + 1 }));
    if (rest > total * 0.001) slices.push({ c: "", v: rest, label: "Other partners", col: PIE_OTHER });
    const W = 300, R = 132, r0 = 72, svgP = d3.select("#pie-chart").attr("viewBox", `${-W / 2} ${-W / 2} ${W} ${W}`).attr("aria-label", $("pie-title").textContent);
    svgP.selectAll("*").remove();
    const arc = d3.arc().innerRadius(r0).outerRadius(d => d.data.c && d.data.c === S.sel ? R + 8 : R).padAngle(.012).cornerRadius(3);
    const pie = d3.pie().sort(null).value(d => d.v)(slices);
    const g = svgP.append("g").selectAll("path").data(pie).join("path").attr("d", arc).attr("fill", d => d.data.col)
      .attr("class", d => "pie-slice" + (d.data.c && d.data.c === S.sel ? " sel" : "")).attr("data-c", d => d.data.c);
    g.append("title").text(d => `${d.data.label}: ${(d.data.v / total * 100).toFixed(1)}% (${fmt(d.data.v)})`);
    svgP.append("g").selectAll("text").data(pie.filter(d => d.data.v / total >= 0.05)).join("text").attr("class", "pie-pct")
      .attr("transform", d => `translate(${d3.arc().innerRadius((r0 + R) / 2).outerRadius((r0 + R) / 2).centroid(d)})`).attr("text-anchor", "middle").attr("dy", ".35em")
      .text(d => `${Math.round(d.data.v / total * 100)}%`);
    svgP.append("text").attr("class", "pie-center").attr("text-anchor", "middle").attr("dy", "-.2em").text((HS2[code.slice(0, 2)] || {}).icon || "");
    svgP.append("text").attr("class", "pie-center-v").attr("text-anchor", "middle").attr("dy", "1.1em").text(fmt(total));
    $("pie-legend").innerHTML = slices.map(d => `<li${d.c && DATA.ids[d.c] ? ` data-c="${d.c}" class="${d.c === S.sel ? "sel" : ""}" role="button" tabindex="0" title="Show ${esc(d.label)} on the map"` : ""}>` +
      `<i style="background:${d.col}"></i><span class="pl">${d.rank ? `<small>${d.rank}.</small> ` : ""}${esc(d.label)}</span><b>${(d.v / total * 100).toFixed(1)}%</b><span class="pv">${fmt(d.v)}</span></li>`).join("");
    $("pie-legend").querySelectorAll("li[data-c]").forEach(li => {
      const c = li.dataset.c, on = v => svgP.selectAll(".pie-slice").classed("dim", function () { return v && this.dataset.c !== c; });
      li.onmouseenter = () => on(true); li.onmouseleave = () => on(false);
      li.onclick = () => { if (c !== S.sel) select(c); }; li.onkeydown = e => { if (e.key === "Enter" && c !== S.sel) select(c); };
    });
    const selShare = S.sel && rows.find(r => r[0] === S.sel);
    $("pie-note").textContent = (S.sel && S.sel !== "LU" ? (selShare ? `${name(S.sel)}: ${(selShare[1] / total * 100).toFixed(1)}% of the total, #${rows.indexOf(selShare) + 1} ${S.flow === "Exports" ? "destination" : "supplier"}. ` : `${name(S.sel)} is not ${deep ? "a partner" : "among the 10 largest partners"} for this product in this period. `) : "") +
      (deep ? `Calendar year ${yr}, all partners, loaded live from Eurostat. ` : "") + "Follows the map's timeline, measure and the product you open. Click a partner to show it on the map.";
    if (reveal) box.scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "nearest" });
  }).catch(err => { if (pieCode() === code) { $("pie-sub").textContent = what; $("pie-note").textContent = `Could not load the partner shares: ${err.message}`; } });
}
$("pie-close").onclick = () => { S.pie = null; drawPie(false); };

/* ---------- category data (one script per HS2 chapter, loaded on first use by the partner chart) ---------- */
function loadProduct(code) {
  if (code === "TOTAL") return Promise.resolve(CORE.total);
  if (window.LUX_PRODUCTS && window.LUX_PRODUCTS[code]) return Promise.resolve(window.LUX_PRODUCTS[code]);
  return new Promise((resolve, reject) => {
    const s = document.createElement("script");
    s.src = `data/js/products/${code}.js`;
    s.onload = () => resolve(window.LUX_PRODUCTS[code]);
    s.onerror = () => reject(new Error(`Missing data/js/products/${code}.js`));
    document.head.appendChild(s);
  });
}
/* ---------- boot ---------- */
$("eyebrow").textContent = `Luxembourg · ${DATA.product}`;
buildIdx(); S.pos = IDX.length - 1;
d3.json(WORLD_URL).then(world => {
  features = topojson.feature(world, world.objects.countries).features.filter(f => f.id !== "010");   // drop Antarctica
  features.forEach(f => { byId.set(f.id, f); mainPart.set(f.id, largestPolygon(f)); });
  gLand.selectAll("path").data(features).join("path").attr("class", "country");
  $("loading").remove();
  resize(); drawSpark(); update(false);
  new ResizeObserver(() => { resize(); drawSpark(); S.focusKey = ""; update(false); }).observe($("mapwrap"));
}).catch(() => { $("loading").textContent = "Could not load the world map (needs an internet connection to cdn.jsdelivr.net)."; });
})();
