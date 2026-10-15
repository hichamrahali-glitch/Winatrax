/* Country comparison: imports and exports per inhabitant for the 28 countries reporting to
   Eurostat's EU trade dataset (EU27 and the United Kingdom), year by year, ranked by imports per
   inhabitant. Exports grow to the left, imports to the right; Luxembourg is pinned to the top row.
   The country groups in the data are not shown; EU27 only provides the dashed reference lines.
   Reads window.LUX.countries from data/js/core.js (built by scripts/build-data.mjs):
   {years, series: {code: {value|quantity: {Exports, Imports}, pop}}, names, groups, reference}.
   Trade in million EUR and thousand tonnes; per inhabitant = trade / population. */
(() => {
const CORE = window.LUX;
const $ = id => document.getElementById(id);
if (!CORE || !CORE.countries) return;
const CMP = CORE.countries, YEARS = CMP.years.map(String), GROUPS = CMP.groups || {}, REF = CMP.reference;
const S = { measure: "value", scale: "pc", rank: "im", pos: YEARS.length - 1, playing: false, speed: 1 };
const ROW = 26, M = { t: 34, r: 92, b: 28, l: 190 };
const RANK_BY = { im: d => d.im, ex: d => d.ex, tot: d => d.ex + d.im };
const RANK_TEXT = { im: "imports", ex: "exports", tot: "total trade" };
let built = false, W = 900, timer = null;

const esc = s => String(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const name = c => CMP.names[c] || CORE.names[c] || c;
const isGroup = c => c in GROUPS;
function flag(code) {   // emoji flag from a 2-letter code; the EU flag for the groups
  if (isGroup(code)) return "🇪🇺";
  const c = { EL: "GR", UK: "GB", XS: "RS" }[code] || code;
  return /^[A-Z]{2}$/.test(c) ? String.fromCodePoint(...[...c].map(ch => 0x1f1e6 + ch.charCodeAt(0) - 65)) : "";
}
function fmt(v) {
  if (v == null) return "–";
  if (S.scale === "pc") return S.measure === "value" ? `€${d3.format(",.0f")(v)}` : `${v.toFixed(1)} t`;
  if (S.measure === "value") return v >= 1000 ? `€${(v / 1000).toFixed(1)} bn` : v >= 1 ? `€${v.toFixed(0)} m` : `€${(v * 1000).toFixed(0)} k`;
  return v >= 1000 ? `${(v / 1000).toFixed(1)} Mt` : v >= 10 ? `${v.toFixed(0)} kt` : `${v.toFixed(1)} kt`;
}
// per inhabitant: million EUR -> EUR, thousand tonnes -> tonnes, divided by population
const perCap = (v, pop) => v == null || !pop ? null : S.measure === "value" ? v * 1e6 / pop : v * 1000 / pop;

function point(c, i) {
  const s = CMP.series[c];
  let ex = s[S.measure].Exports[i], im = s[S.measure].Imports[i];
  if (S.scale === "pc") { ex = perCap(ex, s.pop[i]); im = perCap(im, s.pop[i]); }
  return ex == null || im == null ? null : { c, ex, im, pop: s.pop[i] };
}
function rowsFor(i) {   // countries with data that year: Luxembourg first, then by rank
  const key = RANK_BY[S.rank], cs = [];
  for (const c of Object.keys(CMP.series)) { if (isGroup(c)) continue; const p = point(c, i); if (p) cs.push(p); }
  cs.sort((a, b) => key(b) - key(a)); cs.forEach((d, k) => d.rank = k + 1);
  return [...cs.filter(d => d.c === "LU"), ...cs.filter(d => d.c !== "LU")];
}
const reference = i => (REF && CMP.series[REF] ? point(REF, i) : null);
function maxAll() {   // fixed scale over all years so bars compare across time
  let m = 0;
  YEARS.forEach((y, i) => rowsFor(i).forEach(d => { m = Math.max(m, d.ex, d.im); }));
  return m || 1;
}

let svg, gGrid, gRows, gAvg, x, H;
const nCountries = Object.keys(CMP.series).filter(c => !isGroup(c)).length;
const rowY = k => M.t + k * ROW;
function build() {
  const host = $("cmp-chart");
  W = Math.max(600, host.clientWidth);
  H = M.t + M.b + nCountries * ROW;
  host.innerHTML = "";
  svg = d3.select(host).append("svg").attr("viewBox", `0 0 ${W} ${H}`).attr("role", "img").attr("aria-label", "Exports and imports per inhabitant by reporter");
  svg.append("text").attr("class", "cmp-axis-t").attr("x", M.l + (W - M.l - M.r) / 4).attr("y", 16).attr("text-anchor", "middle").text("◀ Exports");
  svg.append("text").attr("class", "cmp-axis-t").attr("x", M.l + 3 * (W - M.l - M.r) / 4).attr("y", 16).attr("text-anchor", "middle").text("Imports ▶");
  gGrid = svg.append("g"); gAvg = svg.append("g"); gRows = svg.append("g");
  built = true;
  rescale();
}
function rescale() {
  const mid = M.l + (W - M.l - M.r) / 2, half = (W - M.l - M.r) / 2 - 8;
  x = { mid, len: d3.scaleLinear([0, maxAll()], [0, half]) };
  const ticks = x.len.ticks(3).filter(t => t > 0);
  gGrid.selectAll("*").remove();
  ticks.forEach(t => [-1, 1].forEach(sgn => {
    const X = mid + sgn * x.len(t);
    gGrid.append("line").attr("x1", X).attr("x2", X).attr("y1", M.t - 6).attr("y2", H - M.b).attr("class", "cmp-grid");
    gGrid.append("text").attr("x", X).attr("y", H - 8).attr("text-anchor", "middle").attr("class", "cmp-tick").text(fmt(t));
  }));
  gGrid.append("line").attr("x1", mid).attr("x2", mid).attr("y1", M.t - 6).attr("y2", H - M.b).attr("class", "cmp-zero");
}

function label(d) {
  return d.c === "LU" ? `${flag(d.c)} ${name(d.c)}  (#${d.rank})` : `${d.rank}. ${flag(d.c)} ${name(d.c)}`;
}
function draw(animate) {
  if (!built) return;
  const i = S.pos, rows = rowsFor(i), dur = animate ? Math.min(700, 600 / S.speed) : 0, mid = x.mid;
  const g = gRows.selectAll("g.cmp-row").data(rows, d => d.c);
  const en = g.enter().append("g").attr("class", d => "cmp-row" + (d.c === "LU" ? " lu" : "")).attr("transform", (d, k) => `translate(0,${rowY(k)})`);
  en.append("rect").attr("class", "cmp-hit").attr("x", 0).attr("width", W).attr("height", ROW);
  en.append("text").attr("class", "cmp-name").attr("x", M.l - 10).attr("y", ROW / 2 + 4).attr("text-anchor", "end");
  en.append("rect").attr("class", "cmp-ex").attr("y", 4).attr("height", ROW - 8).attr("rx", 3).attr("x", mid).attr("width", 0);
  en.append("rect").attr("class", "cmp-im").attr("y", 4).attr("height", ROW - 8).attr("rx", 3).attr("x", mid).attr("width", 0);
  en.append("text").attr("class", "cmp-val ex").attr("y", ROW / 2 + 4).attr("text-anchor", "end");
  en.append("text").attr("class", "cmp-val im").attr("y", ROW / 2 + 4);
  en.on("pointermove", (ev, d) => showTip(ev, d)).on("pointerleave", () => { $("cmp-tip").hidden = true; });
  g.exit().remove();
  const all = en.merge(g);
  all.transition().duration(dur).ease(d3.easeCubicInOut).attr("transform", d => `translate(0,${rowY(rows.indexOf(d))})`);
  all.select(".cmp-name").text(label);
  all.select(".cmp-ex").transition().duration(dur).attr("x", d => mid - x.len(d.ex)).attr("width", d => x.len(d.ex));
  all.select(".cmp-im").transition().duration(dur).attr("x", mid).attr("width", d => x.len(d.im));
  all.select(".cmp-val.ex").text(d => fmt(d.ex)).transition().duration(dur).attr("x", d => mid - x.len(d.ex) - 5);
  all.select(".cmp-val.im").text(d => fmt(d.im)).transition().duration(dur).attr("x", d => mid + x.len(d.im) + 5);

  // EU27 reference lines
  const ref = reference(i), H2 = M.t + rows.length * ROW;
  const lines = ref ? [{ k: "ex", X: mid - x.len(ref.ex), v: ref.ex }, { k: "im", X: mid + x.len(ref.im), v: ref.im }] : [];
  const a = gAvg.selectAll("g").data(lines, d => d.k);
  const ae = a.enter().append("g");
  ae.append("line").attr("class", "cmp-avg").attr("y1", M.t - 6);
  ae.append("text").attr("class", "cmp-avg-t").attr("y", M.t - 10).attr("text-anchor", "middle");
  a.exit().remove();
  const am = ae.merge(a);
  am.select("line").attr("y2", H2).transition().duration(dur).attr("x1", d => d.X).attr("x2", d => d.X);
  am.select("text").text(d => `EU27 ${fmt(d.v)}`).transition().duration(dur).attr("x", d => d.X);

  $("cmp-year").textContent = YEARS[i];
  $("cmp-scrub").value = i;
}

function showTip(ev, d) {
  const tip = $("cmp-tip"), b = d.ex - d.im, r = $("cmp-chart").getBoundingClientRect(), i = S.pos, s = CMP.series[d.c];
  tip.innerHTML = `<b>${flag(d.c)} ${esc(name(d.c))}</b> · #${d.rank} by ${RANK_TEXT[S.rank]} per inhabitant, ${YEARS[i]}<br>` +
    `Imports <b>${fmt(d.im)}</b> · Exports <b>${fmt(d.ex)}</b>${S.scale === "pc" ? " per inhabitant" : ""}<br>` +
    `<span class="m">Balance ${b >= 0 ? "+" : "−"}${fmt(Math.abs(b))} · population ${d3.format(",")(s.pop[i])}</span>`;
  tip.hidden = false;
  tip.style.left = Math.min(r.width - tip.offsetWidth - 8, ev.clientX - r.left + 14) + "px";
  tip.style.top = (ev.clientY - r.top - 60) + "px";
}

/* ---------- controls ---------- */
function seg(id, k) {
  const btns = document.querySelectorAll(`#${id} button`);
  btns.forEach(b => { b.setAttribute("aria-pressed", b.dataset.v === S[k]); b.onclick = () => { S[k] = b.dataset.v; btns.forEach(o => o.setAttribute("aria-pressed", o === b)); rescale(); draw(true); }; });
}
seg("cmp-measure", "measure");
const scrub = $("cmp-scrub");
scrub.max = YEARS.length - 1; scrub.value = S.pos;
$("cmp-t0").textContent = YEARS[0]; $("cmp-t1").textContent = YEARS[YEARS.length - 1];
scrub.oninput = () => { stop(); S.pos = +scrub.value; draw(true); };
$("cmp-speed").onchange = e => S.speed = +e.target.value;
const ICON_PLAY = '<path d="M7 4.5v15l13-7.5z"/>', ICON_PAUSE = '<path d="M6 4h4.5v16H6zM13.5 4H18v16h-4.5z"/>';
function tick() { if (S.pos >= YEARS.length - 1) { stop(); return; } S.pos++; draw(true); timer = setTimeout(tick, 1100 / S.speed); }
function play() { if (S.pos >= YEARS.length - 1) S.pos = 0; S.playing = true; $("cmp-play").setAttribute("aria-label", "Pause"); $("cmp-ico").innerHTML = ICON_PAUSE; draw(true); timer = setTimeout(tick, 1100 / S.speed); }
function stop() { S.playing = false; clearTimeout(timer); $("cmp-play").setAttribute("aria-label", "Play"); $("cmp-ico").innerHTML = ICON_PLAY; }
$("cmp-play").onclick = () => S.playing ? stop() : play();
document.addEventListener("keydown", e => {
  if (window.ActiveView !== "cmp" || ["INPUT", "SELECT"].includes(e.target.tagName)) return;
  if (e.code === "Space") { e.preventDefault(); S.playing ? stop() : play(); }
  if (e.code === "ArrowRight") { stop(); S.pos = Math.min(YEARS.length - 1, S.pos + 1); draw(true); }
  if (e.code === "ArrowLeft") { stop(); S.pos = Math.max(0, S.pos - 1); draw(true); }
});

// Built the first time the tab is shown (it needs a width), rebuilt on resize
window.CountryComparison = {
  show() { if (!built || Math.abs($("cmp-chart").clientWidth - W) > 4) { build(); } draw(false); },
  hide() { stop(); },
};
new ResizeObserver(() => { if (built && Math.abs($("cmp-chart").clientWidth - W) > 4) { build(); draw(false); } }).observe($("cmp-chart"));
})();
