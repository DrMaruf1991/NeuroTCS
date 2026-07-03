/* NeuroTCS live demo — frontend logic. No external libraries.
   Calls the FastAPI backend (results only) and renders cards + an SVG cTCS chart. */
"use strict";

const SVGNS = "http://www.w3.org/2000/svg";
const fmt6 = (x) => (x == null ? "—" : Number(x).toFixed(6));
const fmt4 = (x) => (x == null ? "—" : Number(x).toFixed(4));
const pct = (x) => (x == null ? "—" : (100 * x).toFixed(2) + "%");
const intc = (x) => (x == null ? "—" : Number(x).toLocaleString());

// In-memory state: cohort_id -> { spec, result|null, status }
const STATE = new Map();
let COHORT_ORDER = [];

document.addEventListener("DOMContentLoaded", init);

async function init() {
  bindThemeFromSystem();
  document.getElementById("run-all").addEventListener("click", runAll);
  try {
    const res = await fetch("/api/cohorts").then((r) => r.json());
    setEnv(true, res.neurotcs_version);
    document.getElementById("foot-ver").textContent =
      "engine: neurotcs " + res.neurotcs_version;
    COHORT_ORDER = res.cohorts.map((c) => c.cohort_id);
    for (const c of res.cohorts) STATE.set(c.cohort_id, { spec: c, result: null, status: "idle" });
    renderCards();
    renderChart();
    const nAvail = res.cohorts.filter((c) => c.available).length;
    document.getElementById("run-all-hint").textContent =
      `${nAvail}/${res.cohorts.length} cohorts have data configured on this server.`;
  } catch (e) {
    setEnv(false, "unreachable");
    document.getElementById("run-all-hint").textContent = "Backend unreachable.";
  }
}

function bindThemeFromSystem() {
  const mq = window.matchMedia("(prefers-color-scheme: dark)");
  const apply = () =>
    document.documentElement.setAttribute("data-theme", mq.matches ? "dark" : "light");
  apply();
  mq.addEventListener("change", () => { apply(); renderChart(); });
}

function setEnv(ok, text) {
  const dot = document.getElementById("env-dot");
  const t = document.getElementById("env-text");
  dot.className = "dot " + (ok ? "ok" : "err");
  t.textContent = ok ? `engine online · neurotcs ${text}` : "backend " + text;
}

async function runAll() {
  const btn = document.getElementById("run-all");
  btn.disabled = true;
  const ids = COHORT_ORDER.filter((id) => STATE.get(id).spec.available);
  await Promise.all(ids.map((id) => runOne(id)));
  btn.disabled = false;
}

async function runOne(cohortId) {
  const st = STATE.get(cohortId);
  if (!st || !st.spec.available) return;
  st.status = "running";
  st.error = null;
  renderCard(cohortId);
  try {
    const resp = await fetch(`/api/audit/${cohortId}`, { method: "POST" });
    const body = await resp.json();
    if (!resp.ok) throw new Error(body.detail || `HTTP ${resp.status}`);
    st.result = body;
    st.status = body.n_flagged > 0 ? "flags" : "clean";
  } catch (e) {
    st.status = "error";
    st.error = String(e.message || e);
  }
  renderCard(cohortId);
  renderChart();
}

/* ---------- cards ---------- */
function renderCards() {
  const host = document.getElementById("cards");
  host.innerHTML = "";
  for (const id of COHORT_ORDER) {
    const el = document.createElement("div");
    el.className = "card";
    el.id = "card-" + id;
    host.appendChild(el);
    renderCard(id);
  }
}

function statusPill(st) {
  switch (st.status) {
    case "running": return `<span class="status-pill st-run">running…</span>`;
    case "clean": return `<span class="status-pill st-clean">clean</span>`;
    case "flags": return `<span class="status-pill st-flags">flags present</span>`;
    case "error": return `<span class="status-pill st-na">error</span>`;
    default:
      return st.spec.available
        ? `<span class="status-pill st-idle">ready</span>`
        : `<span class="status-pill st-na">no data</span>`;
  }
}

function parityBadge(st) {
  if (!st.result) return `<span class="parity pending">parity: —</span>`;
  const p = st.result.parity;
  return p.parity_holds
    ? `<span class="parity ok" title="cTCS within 0.0005 and counts exact vs the locked CLI invariant">✓ parity holds</span>`
    : `<span class="parity bad" title="live result differs from the locked invariant">✕ parity off</span>`;
}

function renderCard(id) {
  const st = STATE.get(id);
  const el = document.getElementById("card-" + id);
  if (!el) return;
  const s = st.spec, r = st.result, L = s.locked;

  const pmid = r && r.citation_pmid;
  const doi = r && r.citation_doi;
  const citeRows = r ? `
    <div class="row"><span class="lbl">rule pack</span>
      <span class="mono">${r.rulepack_id || "—"}</span></div>
    <div class="row"><span class="lbl">PMID</span>
      ${pmid ? `<a href="https://pubmed.ncbi.nlm.nih.gov/${pmid}/" target="_blank" rel="noopener" class="mono">${pmid}</a>` : "—"}</div>
    <div class="row"><span class="lbl">DOI</span>
      ${doi ? `<a href="https://doi.org/${doi}" target="_blank" rel="noopener" class="mono">${doi}</a>` : "—"}</div>
  ` : `
    <div class="row"><span class="lbl">rules</span>
      <span class="mono">NIA-AA 2018 (cited on run)</span></div>`;

  const ctcsVal = r ? fmt6(r.ctcs) : fmt6(L.ctcs);
  const ci = r && r.ci_low != null ? `<small> [${fmt4(r.ci_low)}–${fmt4(r.ci_high)}]</small>` : "";
  const transVal = r ? intc(r.n_transitions) : intc(L.n_transitions);
  const flagVal = r ? intc(r.n_flagged) : intc(L.n_flagged);
  const flagRate = r ? pct(r.flagged_rate) : pct(L.n_flagged / L.n_transitions);
  const preface = r ? "" : `<small> (locked)</small>`;

  el.innerHTML = `
    <div class="card-top">
      <div>
        <h3>${s.display_name}</h3>
        <div class="note">${s.note}</div>
      </div>
      ${statusPill(st)}
    </div>

    <div class="metrics">
      <div class="metric">
        <div class="k">cTCS</div>
        <div class="v">${ctcsVal}${preface}${ci}</div>
      </div>
      <div class="metric">
        <div class="k">Transitions</div>
        <div class="v">${transVal}</div>
      </div>
      <div class="metric">
        <div class="k">Flagged</div>
        <div class="v">${flagVal} <small>(${flagRate})</small></div>
      </div>
      <div class="metric">
        <div class="k">Status</div>
        <div class="v" style="font-size:15px;">${r ? r.status : (s.available ? "not run" : "unavailable")}</div>
      </div>
    </div>

    <div class="cite">${citeRows}</div>

    ${r ? `<div><div class="k" style="font-size:11.5px;color:var(--muted);text-transform:uppercase;letter-spacing:.4px;margin-bottom:4px;">audit id — same input, same id</div>
      <div class="auditid">${r.audit_id || "—"}</div></div>` : ""}

    ${st.error ? `<div class="errline">${st.error}</div>` : ""}

    <div class="card-actions">
      <button class="btn btn-sm btn-primary" ${(!s.available || st.status === "running") ? "disabled" : ""}
        onclick="window.__runOne('${id}')">
        ${st.status === "running" ? "Auditing…" : (r ? "Re-run audit" : "Run audit")}
      </button>
      ${parityBadge(st)}
    </div>
  `;
}
window.__runOne = runOne;

/* ---------- SVG chart: cTCS with CI whiskers, zoomed to the data band ---------- */
function renderChart() {
  const svg = document.getElementById("chart");
  if (!svg) return;
  while (svg.firstChild) svg.removeChild(svg.firstChild);

  const W = 760, H = 340;
  const m = { top: 20, right: 20, bottom: 54, left: 62 };
  const iw = W - m.left - m.right, ih = H - m.top - m.bottom;

  const ids = COHORT_ORDER.length ? COHORT_ORDER : [];
  // y-domain: zoom into the near-1.0 band so 0.985–0.997 differences are visible.
  let lo = 1, hi = 1;
  for (const id of ids) {
    const st = STATE.get(id);
    const L = st.spec.locked;
    lo = Math.min(lo, L.ctcs);
    hi = Math.max(hi, L.ctcs);
    if (st.result) {
      lo = Math.min(lo, st.result.ci_low ?? st.result.ctcs);
      hi = Math.max(hi, st.result.ci_high ?? st.result.ctcs);
    }
  }
  lo = Math.floor((lo - 0.003) * 1000) / 1000;
  hi = Math.min(1.0, Math.ceil((hi + 0.001) * 1000) / 1000);
  if (hi <= lo) { hi = 1.0; lo = 0.98; }

  const x = (i) => m.left + (iw * (i + 0.5)) / Math.max(ids.length, 1);
  const y = (v) => m.top + ih * (1 - (v - lo) / (hi - lo));
  const col = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();

  // gridlines + y ticks
  const nTicks = 5;
  for (let t = 0; t <= nTicks; t++) {
    const v = lo + ((hi - lo) * t) / nTicks;
    const yy = y(v);
    line(svg, m.left, yy, W - m.right, yy, col("--line"), 1);
    text(svg, m.left - 10, yy + 4, v.toFixed(3), 11, col("--muted"), "end");
  }
  // axis title
  text(svg, 16, m.top + ih / 2, "cTCS", 12, col("--muted"), "middle", -90);

  const band = iw / Math.max(ids.length, 1);
  const barW = Math.min(30, band * 0.34);

  ids.forEach((id, i) => {
    const st = STATE.get(id);
    const cx = x(i);
    const L = st.spec.locked;

    // locked marker: a faint reference bar to the locked cTCS
    const yl = y(L.ctcs);
    rect(svg, cx - barW - 3, yl, barW, m.top + ih - yl, col("--locked"), 0.55);

    // live result bar + CI whisker
    if (st.result && st.result.ctcs != null) {
      const yv = y(st.result.ctcs);
      rect(svg, cx + 3, yv, barW, m.top + ih - yv, col("--brand"), 1);
      // CI whisker
      if (st.result.ci_low != null && st.result.ci_high != null) {
        const wx = cx + 3 + barW / 2;
        const yhi = y(st.result.ci_high), ylo = y(st.result.ci_low);
        line(svg, wx, yhi, wx, ylo, col("--ci"), 2.5);
        line(svg, wx - 5, yhi, wx + 5, yhi, col("--ci"), 2.5);
        line(svg, wx - 5, ylo, wx + 5, ylo, col("--ci"), 2.5);
      }
      // value label above the live bar
      text(svg, cx + 3 + barW / 2, yv - 6, fmt4(st.result.ctcs), 10.5, col("--ink"), "middle");
    } else {
      // no live run yet: dashed cap on the locked bar
      text(svg, cx - barW / 2 - 3, yl - 6, fmt4(L.ctcs), 10, col("--muted"), "middle");
    }

    // x label
    text(svg, cx, H - m.bottom + 20, st.spec.display_name, 12, col("--ink"), "middle");
    const stt = st.status === "running" ? "running…"
      : st.result ? `${intc(st.result.n_flagged)} flagged`
      : (st.spec.available ? "not run" : "no data");
    text(svg, cx, H - m.bottom + 36, stt, 10.5, col("--muted"), "middle");
  });

  // baseline
  line(svg, m.left, m.top + ih, W - m.right, m.top + ih, col("--muted"), 1);
}

/* svg helpers */
function line(svg, x1, y1, x2, y2, stroke, w) {
  const e = document.createElementNS(SVGNS, "line");
  e.setAttribute("x1", x1); e.setAttribute("y1", y1);
  e.setAttribute("x2", x2); e.setAttribute("y2", y2);
  e.setAttribute("stroke", stroke); e.setAttribute("stroke-width", w);
  svg.appendChild(e);
}
function rect(svg, x, y, w, h, fill, op) {
  const e = document.createElementNS(SVGNS, "rect");
  e.setAttribute("x", x); e.setAttribute("y", y);
  e.setAttribute("width", Math.max(0, w)); e.setAttribute("height", Math.max(0, h));
  e.setAttribute("rx", 2.5); e.setAttribute("fill", fill);
  e.setAttribute("fill-opacity", op == null ? 1 : op);
  svg.appendChild(e);
}
function text(svg, x, y, s, size, fill, anchor, rot) {
  const e = document.createElementNS(SVGNS, "text");
  e.setAttribute("x", x); e.setAttribute("y", y);
  e.setAttribute("font-size", size); e.setAttribute("fill", fill);
  e.setAttribute("text-anchor", anchor || "start");
  e.setAttribute("font-family", "-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif");
  if (rot) e.setAttribute("transform", `rotate(${rot} ${x} ${y})`);
  e.textContent = s;
  svg.appendChild(e);
}
