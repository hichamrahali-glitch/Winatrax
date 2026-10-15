const DATA = /*__DATA__*/null;
const WORLD_URL = "https://cdn.jsdelivr.net/npm/world-atlas@2.0.2/countries-50m.json";
const LUX = [6.13, 49.61];
const MON = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
const $ = id => document.getElementById(id);

if (!DATA) {
  $("loading").textContent = "No data: open the World map tab in the dashboard or export a prepared map page.";
  throw new Error("no data");
}

const S = { flow: DATA.init.flow, measure: DATA.init.measure, step: "Yearly", speed: 1, pos: 0, playing: false, auto: true, focusKey: "", sel: null, chap: null };
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
const periodLabel = f => `12 months to ${MON[+f.slice(5) - 1]} ${f.slice(0, 4)}`;

/* ---------- frames for the chosen step ---------- */
let IDX = [];
function buildIdx() {
  const n = FR.length;
  IDX = FR.map((f, i) => i).filter(i => S.step === "Monthly" || FR[i].slice(5) === "12");
  if (IDX[IDX.length - 1] !== n - 1) IDX.push(n - 1);
  $("scrub").max = IDX.length - 1;
  $("t0").textContent = FR[IDX[0]].slice(0, 4); $("t1").textContent = periodLabel(FR[n - 1]).replace("12 months to ", "");
}
const frame = () => IDX[S.pos];

/* ---------- map ---------- */
const svg = d3.select("#map"), gZoom = svg.append("g"), gLand = gZoom.append("g"), gOver = svg.append("g"), gFlows = gOver.append("g"), gDet = gOver.append("g"), gLux = gOver.append("g"), gLabels = gOver.append("g");
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
  const k = Math.max(1, Math.min(60, Math.min((W - 2 * padX) / Math.max(1, x1 - x0), (H - 2 * padY) / Math.max(1, y1 - y0))));
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
function drawLux(lux) {
  const lx = gLux.selectAll("g").data([0]).join(enter => { const g = enter.append("g"); g.append("circle").attr("class", "luxring").attr("r", 9); g.append("circle").attr("class", "luxdot").attr("r", 5.5); g.append("text").attr("class", "luxlbl").attr("x", 9).attr("y", -9).text("Luxembourg"); return g; });
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
  const arcs = [{ k: "exp", d: curve(lux, a), v: ex }, { k: "imp", d: curve(a, lux), v: im }].filter(r => r.v > 0);
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
  const all = [...boxes, { fixed: true, x: lux[0] - 10, y: lux[1] - 24, w: 98, h: 34 }];
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
function drawPanel(cur) {
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
function goodsList(code, flow, yr) {
  const e = PP[code]?.[flow]?.[yr];
  if (!e) return `<p class="empty">No ${flow === "Exports" ? "exports" : "imports"} recorded in ${yr}.</p>`;
  const k = S.measure === "value" ? 1 : 2, total = e[0][k - 1];
  const rows = e[1].map(r => ({ c: r[0], v: r[k] })).filter(r => r.v > 0).sort((a, b) => b.v - a.v).slice(0, 5);
  if (!rows.length || !total) return `<p class="empty">Nothing recorded by ${S.measure === "value" ? "value" : "weight"} in ${yr}.</p>`;
  const col = flow === "Exports" ? "var(--exp)" : "var(--imp)", max = rows[0].v, rest = total - d3.sum(rows, r => r.v);
  const can = !!TREE[code];
  return `<ol>${rows.map((r, j) => { const h = HS2[r.c] || {}; return `<li title="${esc(h.full || h.name || r.c)}"${can ? ` class="click" role="button" tabindex="0" data-flow="${flow}" data-chap="${r.c}"` : ""}><span class="rk">${j + 1}</span><span class="gn"><small>${r.c}</small>${h.icon ? h.icon + " " : ""}${esc(h.name || "Chapter " + r.c)}</span><span class="gv">${fmt(r.v)} <small style="color:var(--muted);font-weight:400">${(r.v / total * 100).toFixed(0)}%</small></span><span class="gb"><i style="width:${(r.v / max * 100).toFixed(1)}%;background:${col}"></i></span></li>`; }).join("")}</ol>` +
    (rest > total * 0.005 ? `<div class="other">Other chapters: ${fmt(rest)} (${(rest / total * 100).toFixed(0)}%)</div>` : "");
}
const LEVEL = { 2: "HS2 chapter", 4: "HS4 heading", 6: "HS6 subheading", 8: "CN8 product" };
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
    const [, total, kids] = node, max = kids.length ? kids[0][1] : 1, rest = total - d3.sum(kids, k => k[1]);
    const next = kids.length ? LEVEL[kids[0][0].length] : null;
    body = `<div class="dk"><div class="wide"><div class="k">${esc(dir)} · ${T.year}</div><div class="v">${fmt(total)}</div>${code.length === 2 ? `<div class="n">${esc(h.full || h.name || "")}</div>` : ""}</div></div>` +
      (kids.length ? `<section class="goods"><h3><i style="background:${col}"></i>Top ${Math.min(5, kids.length)} · ${next}s</h3><ol>${kids.map(([p, v, sub], j) =>
        `<li class="prod${sub.length ? " click" : ""}"${sub.length ? ` role="button" tabindex="0" data-code="${p}"` : ""} title="${esc(LABELS[p] || p)}"><span class="rk">${j + 1}</span><span class="gn"><small>${p}</small>${esc(LABELS[p] || "Code " + p)}</span><span class="gv">${fmt(v)} <small style="color:var(--muted);font-weight:400">${total ? (v / total * 100).toFixed(0) : 0}%</small></span><span class="gb"><i style="width:${(v / max * 100).toFixed(1)}%;background:${col}"></i></span>${sub.length ? `<span class="leaf">Mainly ${sub[0][0]} · ${esc(LABELS[sub[0][0]] || "")}</span>` : ""}</li>`).join("")}</ol>
        ${rest > total * 0.005 ? `<div class="other">Other: ${fmt(rest)} (${(rest / total * 100).toFixed(0)}%)</div>` : ""}</section>`
        : `<p class="empty">This is the most detailed level: an 8-digit CN product code.</p>`);
  }
  const yr = yearFor(cur.i).yr;
  el.innerHTML = `<button class="back" id="back">← Back</button>
    <nav class="crumbs" aria-label="Product path">${crumbs}</nav>
    <div><h2${code.length > 2 ? ` class="long" title="${esc(LABELS[code] || code)}"` : ""}>${code.length === 2 ? esc(labelOf(code)) : esc(LABELS[code] || code)}</h2><div class="sub">${LEVEL[code.length]} ${code} · ${flow === "Exports" ? "exports to" : "imports from"} ${esc(nm)} · ${S.measure === "value" ? "by value" : "by weight"}</div></div>
    ${body}
    ${T && T.year !== yr ? `<p class="note">Product detail is for ${T.year}, the most detailed year prepared; the map shows ${yr}.</p>` : ""}`;
  $("back").onclick = goUp;
  el.querySelectorAll(".crumb[data-depth]").forEach(b => b.onclick = () => { const k = +b.dataset.depth; if (k === 0) S.chap = null; else S.chap.path = path.slice(0, k); drawDetail(CUR); });
  el.querySelectorAll("li.click").forEach(li => {
    const open = () => { S.chap.path.push(li.dataset.code); drawDetail(CUR); el.scrollTop = 0; };
    li.onclick = open; li.onkeydown = e => { if (e.key === "Enter") open(); };
  });
}
function drawDetail(cur) {
  if (S.chap) { drawChapter(cur); return; }
  const c = S.sel, { yr, partial } = yearFor(cur.i), el = $("detail");
  const tot = fl => { const e = PP[c]?.[fl]?.[yr]; return e ? e[0][S.measure === "value" ? 0 : 1] : 0; };
  const ex = tot("Exports"), im = tot("Imports"), rx = rankIn("Exports", c, cur.i), ri = rankIn("Imports", c, cur.i);
  const nm = name(c), by = S.measure === "value" ? "by value" : "by weight";
  el.innerHTML = c === "LU" ? `<button class="back" id="back">← Top 5</button><h2>Luxembourg</h2><p class="empty">This is the reporter. Pick a partner country on the map.</p>` :
    `<button class="back" id="back">← Top 5</button>
    <div><h2>${esc(nm)}</h2><div class="sub">Calendar year ${yr}${partial ? " (latest full year)" : ""} · ${by} · all goods</div></div>
    <div class="dk">
      <div><div class="k">Imports from ${esc(nm)}</div><div class="v">${fmt(im)}</div><div class="n">${ri ? `#${ri} supplier, ${periodLabel(FR[cur.i]).replace("12 months to ", "year to ")}` : "&nbsp;"}</div></div>
      <div><div class="k">Exports to ${esc(nm)}</div><div class="v">${fmt(ex)}</div><div class="n">${rx ? `#${rx} market, ${periodLabel(FR[cur.i]).replace("12 months to ", "year to ")}` : "&nbsp;"}</div></div>
      ${S.measure === "value" ? `<div class="wide"><div class="k">Trade balance</div><div class="v" style="color:${ex - im >= 0 ? "var(--up)" : "var(--down)"}">${ex - im >= 0 ? "+" : "−"}${fmt(Math.abs(ex - im))}</div><div class="n">${ex - im >= 0 ? "Luxembourg sells more than it buys" : "Luxembourg buys more than it sells"}</div></div>` : ""}
    </div>
    ${S.flow === "Imports"
      ? `<section class="goods"><h3><i style="background:var(--imp)"></i>Luxembourg imports from ${esc(nm)}</h3>${goodsList(c, "Imports", yr)}</section>`
      : `<section class="goods"><h3><i style="background:var(--exp)"></i>Luxembourg exports to ${esc(nm)}</h3>${goodsList(c, "Exports", yr)}</section>`}
    ${TREE[c] ? `<p class="note">Click a category for its top 5 products, then keep clicking to go down to 8-digit products (${TREE[c].year} detail).</p>` : `<p class="note">Product detail is prepared for the 40 largest partners only.</p>`}`;
  $("back").onclick = () => select(null);
  el.querySelectorAll("li.click").forEach(li => {
    const open = () => { S.chap = { flow: li.dataset.flow, path: [li.dataset.chap] }; drawDetail(CUR); el.scrollTop = 0; };
    li.onclick = open; li.onkeydown = e => { if (e.key === "Enter") open(); };
  });
}
function select(code) {
  S.sel = code && code === S.sel ? null : code; S.chap = null;
  const on = !!S.sel;
  $("detail").hidden = !on; $("topkpi").hidden = on; $("list").hidden = on;
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
  sp.on("click", ev => { const [mx] = d3.pointer(ev); stop(); S.pos = Math.round(x.invert(mx)); update(true); });
  el._x = x;
}
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
  const hidden = cur.top.filter(d => !d.id).map(d => name(d.c));
  $("note").textContent = `${S.measure === "value" ? "Value" : "Weight"} of ${S.flow.toLowerCase()} over the previous 12 months. Source: Eurostat Comext DS-045409.` +
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
document.addEventListener("keydown", e => { if (e.key !== "Escape" || !S.sel) return; if (S.chap) goUp(); else select(null); });
document.addEventListener("keydown", e => { if (e.target.tagName === "INPUT" || e.target.tagName === "SELECT") return; if (e.code === "Space") { e.preventDefault(); S.playing ? stop() : play(); } if (e.code === "ArrowRight") { stop(); S.pos = Math.min(IDX.length - 1, S.pos + 1); update(true); } if (e.code === "ArrowLeft") { stop(); S.pos = Math.max(0, S.pos - 1); update(true); } });

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
