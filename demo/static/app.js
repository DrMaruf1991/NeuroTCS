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
  document.documentElement.setAttribute("data-theme", "light");
  document.getElementById("run-all").addEventListener("click", runAll);
  initUpload();
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
    const n = res.cohorts.length;
    document.getElementById("run-all-hint").textContent = nAvail
      ? `${nAvail}/${n} cohorts have DUA data on this host — the rest show locked reference results.`
      : `No DUA data on this host — "Run all audits" shows the locked reference results for all ${n} studies.`;
  } catch (e) {
    setEnv(false, "unreachable");
    document.getElementById("run-all-hint").textContent = "Backend unreachable.";
  }
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
  // Run every cohort. Where the DUA data is present the audit runs live; where it
  // is absent the backend returns the LOCKED REFERENCE result (clearly labelled),
  // so all 5 studies' results are shown either way.
  await Promise.all(COHORT_ORDER.map((id) => runOne(id)));
  btn.disabled = false;
  const anyRef = COHORT_ORDER.some((id) => {
    const r = STATE.get(id).result;
    return r && r.mode === "locked_reference";
  });
  const anyLive = COHORT_ORDER.some((id) => {
    const r = STATE.get(id).result;
    return r && r.mode === "live";
  });
  const hint = document.getElementById("run-all-hint");
  if (anyRef && !anyLive) {
    hint.textContent =
      "Showing the locked reference results — the real, reproduced invariants " +
      "from all 5 studies. This host has no DUA data to recompute live.";
  } else if (anyRef && anyLive) {
    hint.textContent =
      "Live audits where DUA data is present; locked reference results elsewhere.";
  }
}

async function runOne(cohortId) {
  const st = STATE.get(cohortId);
  if (!st) return;
  st.status = "running";
  st.error = null;
  renderCard(cohortId);
  try {
    const resp = await fetch(`/api/audit/${cohortId}`, { method: "POST" });
    const body = await resp.json();
    if (!resp.ok) throw new Error(body.detail || `HTTP ${resp.status}`);
    st.result = body;
    st.reference = body.mode === "locked_reference";
    st.status = st.reference
      ? "reference"
      : (body.n_flagged > 0 ? "flags" : "clean");
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
    case "reference": return `<span class="status-pill st-ref">reference</span>`;
    case "clean": return `<span class="status-pill st-clean">clean</span>`;
    case "flags": return `<span class="status-pill st-flags">flags present</span>`;
    case "error": return `<span class="status-pill st-na">error</span>`;
    default:
      return st.spec.available
        ? `<span class="status-pill st-idle">ready</span>`
        : `<span class="status-pill st-idle">ready · reference</span>`;
  }
}

function parityBadge(st) {
  if (!st.result) return `<span class="parity pending">parity: —</span>`;
  if (st.result.mode === "locked_reference")
    return `<span class="parity ref" title="Reproduced on the private DUA server; shown from the locked invariants, not recomputed on this host">locked reference</span>`;
  const p = st.result.parity;
  return p && p.parity_holds
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
  // "(locked)" tags the pre-run reference number; a reference RESULT is labelled
  // by its status pill + badge, so only tag when nothing has run yet.
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

    ${r ? `<div><div class="auditid-label">audit id — same input, same id</div>
      <div class="auditid">${r.audit_id || "— (not locked for this cohort)"}</div></div>` : ""}

    ${st.reference && r ? `<div class="ref-note">${esc(r.reference_note ||
      "Locked reference — reproduced on the DUA server, not recomputed on this host.")}</div>` : ""}

    ${st.error ? `<div class="errline">${st.error}</div>` : ""}

    <div class="card-actions">
      <button class="btn btn-sm btn-primary" ${st.status === "running" ? "disabled" : ""}
        onclick="window.__runOne('${id}')">
        ${st.status === "running"
          ? "Auditing…"
          : (r ? (st.reference ? "Show reference" : "Re-run audit")
               : (s.available ? "Run audit" : "Show result"))}
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

/* ============================ upload audit ============================ */
const esc = (s) =>
  String(s == null ? "" : s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

let UPLOAD = null; // { file, describe }

function initUpload() {
  const dz = document.getElementById("dropzone");
  const input = document.getElementById("file-input");
  const browse = document.getElementById("browse-btn");
  if (!dz) return;

  const pick = () => input.click();
  dz.addEventListener("click", (e) => { if (e.target !== browse) pick(); });
  browse.addEventListener("click", (e) => { e.stopPropagation(); pick(); });
  dz.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") { e.preventDefault(); pick(); }
  });
  input.addEventListener("change", () => {
    if (input.files && input.files[0]) onFile(input.files[0]);
  });
  ["dragenter", "dragover"].forEach((ev) =>
    dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.add("dragover"); }));
  ["dragleave", "drop"].forEach((ev) =>
    dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.remove("dragover"); }));
  dz.addEventListener("drop", (e) => {
    const f = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
    if (f) onFile(f);
  });
}

const OK_EXT = [".csv", ".tsv", ".txt", ".xlsx", ".xls", ".parquet", ".json", ".jsonl",
  ".ndjson", ".rds", ".rdata", ".rda", ".sav", ".dta", ".sas7bdat", ".zsav", ".zip"];

async function onFile(file) {
  const panel = document.getElementById("upload-panel");
  panel.hidden = false;
  const ext = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
  if (!OK_EXT.includes(ext)) {
    panel.innerHTML = fileHeader(file) +
      `<div class="up-msg err">Unsupported type ${esc(ext)}. Use a tabular file (.csv/.xlsx/.parquet/.json), a statistical file (.rds/.rda/.dta/.sav), or a .zip.</div>`;
    bindClear();
    return;
  }
  UPLOAD = { file, describe: null };
  panel.innerHTML = fileHeader(file) +
    `<div class="up-msg info">Reading file and detecting columns…</div>`;
  bindClear();

  const fd = new FormData();
  fd.append("file", file, file.name);
  try {
    const resp = await fetch("/api/upload/describe", { method: "POST", body: fd });
    const body = await resp.json();
    if (!resp.ok) throw new Error(body.detail || `HTTP ${resp.status}`);
    UPLOAD.describe = body;
    renderMapping(body);
  } catch (e) {
    panel.innerHTML = fileHeader(file) +
      `<div class="up-msg err">${esc(e.message || e)}</div>`;
    bindClear();
  }
}

function fileHeader(file) {
  const kb = file.size < 1024 * 1024
    ? (file.size / 1024).toFixed(0) + " KB"
    : (file.size / 1024 / 1024).toFixed(1) + " MB";
  return `<div class="up-file">
    <span class="fname">${esc(file.name)}</span>
    <span class="fmeta">· ${kb}</span>
    <button class="btn btn-sm clear" id="up-clear">Clear</button>
  </div>`;
}

function bindClear() {
  const c = document.getElementById("up-clear");
  if (c) c.addEventListener("click", () => {
    UPLOAD = null;
    const panel = document.getElementById("upload-panel");
    panel.hidden = true; panel.innerHTML = "";
    document.getElementById("file-input").value = "";
  });
}

function colOptions(cols, selected, includeNone) {
  let html = "";
  if (includeNone) {
    const sel = !selected ? " selected" : "";
    html += `<option value=""${sel}>(none — derive from order)</option>`;
  }
  for (const c of cols) {
    const sel = c === selected ? " selected" : "";
    html += `<option value="${esc(c)}"${sel}>${esc(c)}</option>`;
  }
  return html;
}

function renderMapping(desc) {
  const panel = document.getElementById("upload-panel");
  const sheets = desc.sheets || {};
  const sheetNames = Object.keys(sheets);
  const s = desc.suggested || {};
  const curSheet = s.sheet && sheets[s.sheet] ? s.sheet : sheetNames[0];
  const cols = (sheets[curSheet] && sheets[curSheet].columns) || [];

  const sheetField = sheetNames.length > 1 ? `
    <div class="map-field">
      <label>Sheet</label>
      <select id="m-sheet">${sheetNames.map((n) =>
        `<option value="${esc(n)}"${n === curSheet ? " selected" : ""}>${esc(n)} (${sheets[n].shape[0]}×${sheets[n].shape[1]})</option>`).join("")}</select>
    </div>` : "";

  panel.innerHTML = fileHeader(UPLOAD.file) + `
    <p class="map-hint">Confirm the column mapping. NeuroTCS pre-selected its best
      guess — adjust if needed. <strong>subject id</strong> and <strong>state</strong>
      are required; a visit date is optional (order is derived if omitted).</p>
    <div class="map-grid">
      ${sheetField}
      <div class="map-field">
        <label>Subject id <span class="req">*</span></label>
        <select id="m-subject_id">${colOptions(cols, s.subject_id, false)}</select>
      </div>
      <div class="map-field">
        <label>State / diagnosis <span class="req">*</span></label>
        <select id="m-state">${colOptions(cols, s.state, false)}</select>
      </div>
      <div class="map-field">
        <label>Visit date</label>
        <select id="m-visit_date">${colOptions(cols, s.visit_date, true)}</select>
      </div>
      <div class="map-field">
        <label>Visit</label>
        <select id="m-visit">${colOptions(cols, s.visit, true)}</select>
      </div>
    </div>
    <div id="numeric-warn" class="numeric-warn" hidden></div>
    <label class="norm-toggle">
      <input type="checkbox" id="m-normalize" checked />
      <span>Normalize stage labels to CN/MCI/AD
        <span class="norm-hint">(e.g. “Normal”→CN, “Alzheimer’s disease”→AD; numeric CDR/NACC scores are not converted)</span></span>
    </label>
    <div class="up-actions">
      <button class="btn btn-primary" id="run-upload">Run audit</button>
      <span class="up-msg info" id="up-status"></span>
    </div>
    <div id="up-result"></div>`;

  bindClear();

  // numeric-column guard: warn (live) if the chosen state column looks numeric
  const numericCols = (sheets[curSheet] && sheets[curSheet].numeric_like) || [];
  const stateSel = document.getElementById("m-state");
  const updateNumericWarn = () => {
    const warn = document.getElementById("numeric-warn");
    if (!warn || !stateSel) return;
    if (numericCols.includes(stateSel.value)) {
      warn.hidden = false;
      warn.innerHTML =
        `⚠️ <strong>“${esc(stateSel.value)}” looks numeric.</strong> Raw staging codes
         (e.g. ADNI <span class="mono">1/2/3</span>, CDR <span class="mono">0/0.5/1</span>)
         can be matched to a <em>different</em> published scheme and misinterpreted — a real
         reversal may come back unflagged. Convert to <span class="mono">CN/MCI/AD</span> text
         first. <a href="/guide" target="_blank" rel="noopener">Why →</a>`;
    } else {
      warn.hidden = true;
    }
  };
  if (stateSel) stateSel.addEventListener("change", updateNumericWarn);
  updateNumericWarn();

  const sheetSel = document.getElementById("m-sheet");
  if (sheetSel) sheetSel.addEventListener("change", () => {
    // re-render column dropdowns for the newly selected sheet
    const ns = { ...desc, suggested: { ...s, sheet: sheetSel.value,
      subject_id: null, state: null, visit_date: null, visit: null } };
    renderMapping(ns);
  });

  document.getElementById("run-upload").addEventListener("click", () =>
    runUploadAudit(curSheet));
}

async function runUploadAudit(sheet) {
  const status = document.getElementById("up-status");
  const btn = document.getElementById("run-upload");
  const val = (id) => { const el = document.getElementById(id); return el ? el.value : ""; };
  const mapping = {
    sheet: (document.getElementById("m-sheet") || {}).value || sheet,
    subject_id: val("m-subject_id"),
    state: val("m-state"),
    visit_date: val("m-visit_date") || null,
    visit: val("m-visit") || null,
  };
  if (!mapping.subject_id || !mapping.state) {
    status.className = "up-msg err";
    status.textContent = "Select a subject id and a state column.";
    return;
  }
  btn.disabled = true;
  status.className = "up-msg info";
  status.textContent = "Auditing… (large files take longer)";

  const normEl = document.getElementById("m-normalize");
  const fd = new FormData();
  fd.append("file", UPLOAD.file, UPLOAD.file.name);
  fd.append("mapping", JSON.stringify(mapping));
  fd.append("normalize", normEl && normEl.checked ? "true" : "false");
  try {
    const resp = await fetch("/api/audit/upload", { method: "POST", body: fd });
    const body = await resp.json();
    if (!resp.ok) throw new Error(body.detail || `HTTP ${resp.status}`);
    status.textContent = "";
    renderUploadResult(body);
  } catch (e) {
    status.className = "up-msg err";
    status.textContent = String(e.message || e);
  } finally {
    btn.disabled = false;
  }
}

function renderUploadResult(r) {
  const host = document.getElementById("up-result");
  const ci = r.ci_low != null ? ` [${fmt4(r.ci_low)}–${fmt4(r.ci_high)}]` : "";
  const pmid = r.citation_pmid
    ? `<a href="https://pubmed.ncbi.nlm.nih.gov/${esc(r.citation_pmid)}/" target="_blank" rel="noopener" class="mono">${esc(r.citation_pmid)}</a>` : "—";
  const doi = r.citation_doi
    ? `<a href="https://doi.org/${esc(r.citation_doi)}" target="_blank" rel="noopener" class="mono">${esc(r.citation_doi)}</a>` : "—";
  const statusPill = r.n_flagged > 0
    ? `<span class="status-pill st-flags">flags present</span>`
    : `<span class="status-pill st-clean">clean</span>`;

  const readNote = r.read_mode === "transient_temp_file"
    ? `read via a secure temp file, deleted immediately after parsing`
    : `read in memory — nothing written to disk`;

  const warn = (r.warnings && r.warnings.length)
    ? `<div class="up-warn">${r.warnings.map(esc).join("<br>")}</div>` : "";

  const norm = (r.label_normalization && r.label_normalization.length)
    ? `<div class="up-norm">Normalized stage labels: ${r.label_normalization
        .map((m) => `<span class="mono">${esc(m.raw)}→${esc(m.canonical)}</span>`)
        .join(", ")}</div>` : "";

  const numWarn = r.state_looks_numeric
    ? `<div class="numeric-warn">⚠️ <strong>The state column looked numeric.</strong>
        Raw codes may have been matched to a different published scheme and
        misinterpreted — treat this score with caution and re-run with
        <span class="mono">CN/MCI/AD</span> text.
        <a href="/guide" target="_blank" rel="noopener">Why →</a></div>` : "";

  let flagsTable = "";
  if (r.flags && r.flags.length) {
    const rows = r.flags.map((f) => {
      const tier = f.tier || "";
      return `<tr>
        <td class="mono">${esc(f.subject_id)}</td>
        <td>${esc(f.from)} → ${esc(f.to)}</td>
        <td>${f.delta_days != null ? Math.round(f.delta_days) + "d" : "—"}</td>
        <td class="tier-${esc(tier)}">${esc(tier)}</td>
      </tr>`;
    }).join("");
    flagsTable = `
      <div class="flags-wrap"><table class="flags">
        <thead><tr><th>Subject</th><th>Transition</th><th>Δ</th><th>Tier</th></tr></thead>
        <tbody>${rows}</tbody>
      </table></div>
      ${r.flags_truncated ? `<p class="flags-note">Showing first ${r.flags.length} flags of the full set.</p>` : ""}`;
  }

  host.innerHTML = `
    <div class="up-result">
      <div class="up-result-head">
        <h3>Audit result</h3>
        ${statusPill}
      </div>
      <div class="up-metrics">
        <div class="metric"><div class="k">cTCS</div>
          <div class="v">${fmt6(r.ctcs)}<small>${ci}</small></div></div>
        <div class="metric"><div class="k">Transitions</div>
          <div class="v">${intc(r.n_transitions)}</div></div>
        <div class="metric"><div class="k">Flagged</div>
          <div class="v">${intc(r.n_flagged)} <small>(${pct(r.flagged_rate)})</small></div></div>
      </div>
      ${numWarn}
      ${norm}
      ${warn}
      <div class="cite">
        <div class="row"><span class="lbl">rule pack</span><span class="mono">${esc(r.rulepack_id || "—")}</span></div>
        <div class="row"><span class="lbl">PMID</span>${pmid}</div>
        <div class="row"><span class="lbl">DOI</span>${doi}</div>
      </div>
      <div style="margin-top:12px;">
        <div class="auditid-label">audit id — same input, same id</div>
        <div class="auditid">${esc(r.audit_id || "—")}</div>
      </div>
      <p class="flags-note" style="margin-top:8px;">${esc(readNote)}.</p>
      ${flagsTable ? `<div style="margin-top:16px;"><div class="auditid-label" style="margin-bottom:8px;">flagged transitions (subject ids hashed)</div>${flagsTable}</div>` : ""}
      <div class="up-actions" style="margin-top:16px;">
        <button class="btn btn-sm" id="dl-bundle">Download bundle JSON</button>
      </div>
    </div>`;

  const dl = document.getElementById("dl-bundle");
  if (dl) dl.addEventListener("click", () => {
    const blob = new Blob([JSON.stringify(r.bundle, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = (r.filename || "upload").replace(/\.[^.]+$/, "") + ".bundle.json";
    a.click();
    URL.revokeObjectURL(url);
  });
}
