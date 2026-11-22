// Page logic: collects the inputs, sends them to the Python worker and shows the results.
const $ = (id) => document.getElementById(id);
const form = $("form");
const worker = new Worker("worker.js");
let catalog, defaultRows, rows = [], lastResult = null, revision = 0, pendingRevision = 0, resultRevision = -1;
let workerReady = false, calculating = false;
let patternUrls = [];
const STORAGE_KEY = "asteria-design-v1";
let saved = {};
try { saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}") || {}; } catch { saved = {}; }
const safeSavedInputs = saved.inputs && typeof saved.inputs === "object" ? saved.inputs : {};

const fmt = (x, d = 1) => Number(x).toFixed(d);
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

function fillDefaults(d) {
  $("shape").innerHTML = Object.entries(d.shapes)
    .map(([k, v]) => `<option value="${k}">${esc(v)}</option>`).join("");
  for (const k of ["shape", "mass_g", "speed", "spill", "apogee", "opening_speed", "fabric_g_m2", "seam_mm", "line_factor", "density",
                   "launch_time", "latitude", "longitude"]) {
    form.elements[k].value = d[k];
  }
  for (const [key, value] of Object.entries(safeSavedInputs)) {
    const el = form.elements.namedItem(key);
    if (!el || el.tagName === "BUTTON") continue;
    const initial = el.value;
    el.value = String(value);
    if (!el.checkValidity() || el.value === "") el.value = initial;
  }
}

function params() {
  const p = Object.fromEntries(new FormData(form).entries());
  const component = (r) => ({ ...r, cost_gbp: Parts.lineCost(r) });
  p.components = rows.filter((r) => r.group === "Flight").map(component);
  p.ground = rows.filter((r) => r.group === "Ground").map(component);
  p.materials_cost_gbp = rows.filter((r) => r.group === "Materials").reduce((sum, r) => sum + Parts.lineCost(r), 0);
  return p;
}

async function run() {
  if (!workerReady || calculating || !await partsReady) return;
  if (!form.checkValidity()) { navigateTab("overview"); form.reportValidity(); return; }
  if (!validParts()) return;
  pendingRevision = revision;
  calculating = true;
  updateFreshness();
  $("run").disabled = true;
  $("run").textContent = "Calculating…";
  $("status").textContent = "";
  document.body.classList.add("busy");
  worker.postMessage({ params: params(), sweeps: $("sweeps").checked });
}

const STATUS_ICON = { PASS: "✓", FAIL: "✕", WARN: "!", MANUAL: "○" };

function show(r) {
  const k = r.key;
  const vOk = r.checks.find((c) => c.rule.startsWith("Descent rate 10"))?.status === "PASS";
  $("tiles").innerHTML = [
    ["Descent speed", `${fmt(k.v_ground)} m/s`, `${fmt(k.v_apogee)} m/s at apogee`, vOk ? "PASS" : "FAIL"],
    ["Canopy", `${fmt(k.width_cm)} cm`, `${esc(k.shape)}, ${fmt(k.area_m2, 4)} m², hole ${fmt(k.hole_cm)} cm`],
    ["Ballast", `${fmt(k.ballast_design_g, 0)} g`, `to ${fmt(k.flight_g, 0)} g (${fmt(k.ballast_min_g, 0)} g for 300 g)`],
    ["Descent time", `${fmt(k.descent_s)} s`, `${k.packets} packets at 1 Hz`],
    ["Opening shock", `${fmt(k.opening_n)} N`, "rated 50 N"],
    ["Flight cost", `£${fmt(k.cost_gbp, 2)}`, `of £${fmt(k.budget_gbp, 0)} · ground £${fmt(k.ground_gbp, 2)} extra`, k.cost_gbp <= k.budget_gbp ? "PASS" : "FAIL"],
    ["4G link", `${fmt(k.cell_kbps, 0)} kbps`, `full-rate data live of ~${fmt(k.uplink_kbps, 0)} usable · ${fmt(k.cell_mb)} MB per flight`],
    ...(k.sun_el > 5 ? [["Blue/red signal", `${fmt(Math.abs(k.ratio_signal_pct), 2)} %`, `level sensor · ${fmt(Math.abs(k.ratio_direct_pct))} % in direct sunlight (sun ${fmt(k.sun_el, 0)}° up)`]] : []),
  ].map(([t, v, s, st]) => `<div class="tile"><div class="t">${t}</div><div class="v">${v}</div><div class="s">${s}${st ? ` <span class="badge ${st}">${STATUS_ICON[st]} ${st}</span>` : ""}</div></div>`).join("");

  $("checks").innerHTML = r.checks.map((c) =>
    `<tr><td><span class="badge ${c.status}">${STATUS_ICON[c.status]} ${c.status}</span></td><td>${esc(c.rule)}</td><td class="val">${esc(c.value)}</td></tr>`).join("");

  $("shapes").innerHTML = r.shapes.map((s) =>
    `<tr class="${s.chosen ? "chosen" : ""}"><td>${esc(s.shape)}${s.chosen ? " ★" : ""}</td><td>${fmt(s.cd0, 2)}</td><td>${fmt(s.area_m2, 4)}</td>
     <td>${fmt(s.width_cm)}</td><td>${fmt(s.hole_cm)}</td><td>${fmt(s.mass_g)}</td><td class="dims">${esc(s.dims)}</td></tr>`).join("");

  patternUrls.forEach((url) => URL.revokeObjectURL(url));
  patternUrls = [];
  const svgUrl = (text) => {
    const url = URL.createObjectURL(new Blob([text], { type: "image/svg+xml" }));
    patternUrls.push(url);
    return url;
  };
  const names = Object.keys(r.svgs);
  $("pattern").innerHTML = `<img alt="Canopy cutting pattern" src="${svgUrl(r.svgs["canopy_pattern.svg"])}">`;
  $("downloads").innerHTML = names.map((n) =>
    `<a class="btn" download="${n}" href="${svgUrl(r.svgs[n])}">${n === "canopy_pattern.svg" ? "Full-size SVG" : n.replace("canopy_", "").replace(".svg", "")}</a>`).join("");

  const img = (key, alt) => r.images[key] ? `<img alt="${alt}" src="data:image/png;base64,${r.images[key]}">` : "";
  $("plot-descent").innerHTML = img("descent", "Altitude, speed and swing angle against time");
  $("plot-mission").innerHTML = img("mission", "Expected dimming per wavelength band against the reading error from tilt");
  $("mission-panel").hidden = !r.images.mission;
  $("plot-sweeps").innerHTML = img("speed_vs_area", "Descent speed against canopy area for each shape")
    + img("speed_vs_mass", "Descent speed against flight mass") + img("swing_vs_spill", "Swing settle time and canopy width against spill-hole size");
  $("sweep-panel").hidden = !r.images.speed_vs_area;
  $("summary").textContent = r.summary;
  $("streams").innerHTML = r.streams.map(([name, hz, bytes]) => `<tr><td>${esc(name)}</td><td>${hz}</td><td>${bytes}</td></tr>`).join("");
  $("data-budget").textContent = r.data_budget;
  $("mission-unavailable").hidden = !!r.images.mission;
  lastResult = r;
  resultRevision = pendingRevision;
  $("export-version").textContent = "Calculated " + new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) +
    (resultRevision !== revision ? " · Inputs have since changed." : " · Matches current inputs.");
}

worker.onmessage = (e) => {
  const m = e.data;
  if (m.type === "status") $("status").textContent = m.text;
  if (m.type === "ready") { fillDefaults(m.defaults); renderFabric(m.defaults); workerReady = true; $("fab-run").disabled = false; run(); }
  if (m.type === "layout" || m.type === "layout-error") {
    $("fab-run").disabled = false;
    $("fab-run").textContent = "Build fabric layout";
    if (m.type === "layout") showFabric(m.result); else $("fab-status").textContent = "Error: " + m.text;
    return;
  }
  if (m.type === "result") show(m.result);
  if (m.type === "error") $("status").textContent = "Error: " + m.text;
  if (m.type === "result" || m.type === "error") {
    calculating = false;
    updateFreshness();
    $("run").disabled = !workerReady;
    $("run").textContent = "Calculate";
    document.body.classList.remove("busy");
  }
};

form.addEventListener("submit", (e) => { e.preventDefault(); run(); });


// Linkable tabs with browser history and keyboard navigation.
const tabButtons = [...document.querySelectorAll("[data-tab]")];
function selectTab(name, focus = false) {
  if (!tabButtons.some((b) => b.dataset.tab === name)) name = "overview";
  tabButtons.forEach((b) => {
    const active = b.dataset.tab === name;
    b.setAttribute("aria-selected", String(active));
    b.tabIndex = active ? 0 : -1;
    $("panel-" + b.dataset.tab).hidden = !active;
    if (active && focus) b.focus();
  });
  const wide = name === "parts" || name === "exports";
  $("workspace").classList.toggle("wide", wide);
  form.hidden = wide;
}
function navigateTab(name, focus = false) {
  if (location.hash !== "#" + name) history.pushState(null, "", "#" + name);
  selectTab(name, focus);
}
tabButtons.forEach((button, i) => {
  button.addEventListener("click", () => navigateTab(button.dataset.tab));
  button.addEventListener("keydown", (event) => {
    let next;
    if (event.key === "ArrowRight") next = (i + 1) % tabButtons.length;
    if (event.key === "ArrowLeft") next = (i + tabButtons.length - 1) % tabButtons.length;
    if (event.key === "Home") next = 0;
    if (event.key === "End") next = tabButtons.length - 1;
    if (next !== undefined) { event.preventDefault(); navigateTab(tabButtons[next].dataset.tab, true); }
  });
});
window.addEventListener("hashchange", () => selectTab(location.hash.slice(1)));
window.addEventListener("popstate", () => selectTab(location.hash.slice(1)));
selectTab(location.hash.slice(1));

function updateFreshness() {
  const stale = !!lastResult && resultRevision !== revision;
  $("stale").hidden = !stale;
  $("download-summary").disabled = !lastResult || stale || calculating;
  $("downloads").hidden = !lastResult || stale || calculating;
}
function persist() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({
      inputs: workerReady ? Object.fromEntries(new FormData(form).entries()) : safeSavedInputs,
      parts: Object.fromEntries(rows.map((r) => [r.id, { qty: r.qty, mass_g: r.mass_g, cost_gbp: r.cost_gbp, estimate: r.estimate }]))
    }));
  } catch { $("parts-status").textContent = "Browser storage is unavailable. Export your changes before leaving."; }
}
function changed() { revision++; updateFreshness(); persist(); }
form.addEventListener("input", changed);

function validParts() {
  const invalid = [...$("parts-rows").querySelectorAll("input")].find((el) => !el.checkValidity());
  if (invalid) {
    $("parts-search").value = "";
    $("parts-group").value = "all";
    filterParts();
    navigateTab("parts");
    invalid.reportValidity();
    return false;
  }
  return true;
}
function renderTotals() {
  const t = Parts.totals(rows);
  $("parts-totals").innerHTML = [
    ["Flight + recovery", t.flight, "of £" + fmt(catalog.budget_gbp, 0) + " flight budget"],
    ["Ground equipment", t.ground, "Separate from the flight budget"],
    ["Total planned spend", t.total, "Planning allowance · excludes shipping"]
  ].map(([label, value, detail]) => '<div class="tile"><div class="t">' + label + '</div><div class="v">£' + fmt(value, 2) + '</div><div class="s">' + detail + '</div></div>').join("");
}
function filterParts() {
  const query = $("parts-search").value.trim().toLowerCase();
  const group = $("parts-group").value;
  let count = 0;
  [...$("parts-rows").children].forEach((tr, i) => {
    const r = rows[i];
    const visible = (group === "all" || r.group === group) && (r.name + " " + r.note).toLowerCase().includes(query);
    tr.hidden = !visible;
    if (visible) count++;
  });
  $("parts-count").textContent = count + " of " + rows.length + " entries";
}
function renderParts() {
  $("parts-rows").innerHTML = rows.map((r, i) => {
    const input = (key, step, value) => '<input type="number" min="0" step="' + step + '" data-i="' + i + '" data-k="' + key + '" value="' + value + '" aria-label="' + esc(r.group + ' ' + r.name + ' ' + key) + '" required>';
    return '<tr><td><strong>' + esc(r.name) + '</strong><div class="supplier-links">' +
      r.links.map((l) => '<a href="' + esc(l.url) + '" target="_blank" rel="noopener noreferrer">' + esc(l.label) + ' ↗</a>').join("") +
      '</div><p class="part-note">' + esc(r.note) + '</p></td><td><span class="group-tag">' + esc(r.group) + '</span></td>' +
      '<td>' + (r.group === "Materials" ? "1 bundle" : input("qty", "1", r.qty)) + '</td>' +
      '<td>' + (r.group === "Flight" ? input("mass_g", "0.1", r.mass_g) : "–") + '</td>' +
      '<td>' + input("cost_gbp", "0.01", r.cost_gbp) + '</td><td>' +
      (r.group === "Flight" ? '<input type="checkbox" data-i="' + i + '" data-k="estimate" ' + (r.estimate ? "checked" : "") + ' aria-label="' + esc(r.name) + ' mass estimated">' : "–") + '</td></tr>';
  }).join("");
  renderTotals(); filterParts();
}
$("parts-rows").addEventListener("input", (event) => {
  const el = event.target;
  if (!el.matches("input[data-i]")) return;
  if (!el.checkValidity()) { revision++; updateFreshness(); return; }
  rows[Number(el.dataset.i)][el.dataset.k] = el.type === "checkbox" ? el.checked : Number(el.value);
  renderTotals(); changed();
});
$("parts-search").addEventListener("input", filterParts);
$("parts-group").addEventListener("change", filterParts);
$("reset-parts").addEventListener("click", () => {
  if (!window.confirm("Restore the default parts quantities, masses and budgets?")) return;
  rows = structuredClone(defaultRows); renderParts(); changed();
});

const partsReady = fetch("parts.json").then(async (response) => {
  if (!response.ok) throw new Error("Could not load the parts catalogue.");
  catalog = await response.json();
  defaultRows = structuredClone(catalog.rows);
  rows = structuredClone(defaultRows);
  for (const r of rows) {
    const edit = saved.parts?.[r.id];
    if (!edit || typeof edit !== "object") continue;
    for (const k of ["qty", "mass_g", "cost_gbp"]) {
      if (typeof edit[k] === "number" && Number.isFinite(edit[k]) && edit[k] >= 0 &&
          (k !== "qty" || Number.isInteger(edit[k])) && r[k] !== null && !(r.group === "Materials" && k === "qty")) r[k] = edit[k];
    }
    if (typeof edit.estimate === "boolean") r.estimate = edit.estimate;
  }
  $("price-note").textContent = catalog.price_note;
  $("parts-status").textContent = "";
  renderParts();
  document.querySelectorAll("[data-export]").forEach((b) => b.disabled = false);
  $("reset-parts").disabled = false;
  return true;
}).catch((error) => {
  $("parts-status").textContent = error.message + " Reload the page to try again.";
  $("status").textContent = "Parts data could not load. Reload to calculate.";
  return false;
});

function download(text, type, filename) {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const a = document.createElement("a");
  a.href = url; a.download = filename; document.body.append(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
document.querySelectorAll("[data-export]").forEach((button) => button.addEventListener("click", async () => {
  if (!catalog || !validParts()) return;
  const kind = button.dataset.export;
  const filename = "asteria-parts-" + new Date().toISOString().slice(0, 10) + ".csv";
  if (kind === "csv") {
    download(Parts.csv(rows), "text/csv;charset=utf-8", filename);
    $("export-status").textContent = "Exported all " + rows.length + " entries with supplier links.";
  } else if (kind === "copy") {
    try {
      await navigator.clipboard.writeText(Parts.tsv(rows));
      $("export-status").textContent = "Copied all parts. Paste into Excel or Google Sheets.";
    } catch {
      download(Parts.tsv(rows), "text/tab-separated-values;charset=utf-8", "asteria-parts.tsv");
      $("export-status").textContent = "Clipboard unavailable; downloaded a spreadsheet-ready TSV instead.";
    }
  } else {
    document.querySelector("#print-frame")?.remove();
    const iframe = document.createElement("iframe");
    iframe.id = "print-frame"; iframe.title = "Printable parts list"; iframe.className = "print-frame";
    iframe.onload = () => { iframe.contentWindow.focus(); iframe.contentWindow.print(); };
    iframe.srcdoc = Parts.printDocument(rows, catalog.price_note);
    document.body.append(iframe);
  }
}));
$("download-summary").addEventListener("click", () => {
  if (lastResult && resultRevision === revision && !calculating) download(lastResult.summary, "text/plain;charset=utf-8", "asteria-design-summary.txt");
});
worker.onerror = () => {
  calculating = false; workerReady = false;
  document.body.classList.remove("busy");
  $("run").disabled = true;
  updateFreshness();
  $("status").textContent = "The calculator could not start. Reload to retry; the parts list and its exports work independently.";
};


// ---------------------------------------------------------------- fabric layout
let fabricUrls = [];
let fabricShapes = {};
function fabricRow(shape, spill, speed, qty = 1, fill = false) {
  const opts = Object.entries(fabricShapes).map(([k, v]) => `<option value="${k}" ${k === shape ? "selected" : ""}>${esc(v)}</option>`).join("");
  const tr = document.createElement("tr");
  tr.innerHTML = `<td><select data-f="shape" aria-label="Shape">${opts}</select></td>
    <td><input type="number" data-f="spill" min="0" max="45" step="1" value="${spill}" aria-label="Spill hole %"></td>
    <td><input type="number" data-f="speed" min="5" max="25" step="0.5" value="${speed}" aria-label="Target speed"></td>
    <td><input type="number" data-f="qty" min="0" max="50" step="1" value="${qty}" aria-label="Copies"></td>
    <td><input type="checkbox" data-f="fill" ${fill ? "checked" : ""} aria-label="Fill the rest of the fabric with this design"></td>
    <td><button type="button" class="secondary fab-del" aria-label="Remove this design">×</button></td>`;
  $("fab-designs").append(tr);
}
function fabricMatrix() {
  const shape = form.elements.shape.value, spill = Number(form.elements.spill.value), speed = form.elements.speed.value;
  $("fab-designs").innerHTML = "";
  for (const k of Object.keys(fabricShapes)) fabricRow(k, spill, speed, 1);           // best shape
  const holes = $("fab-holes").value.split(/[,\s]+/).map(Number).filter((h) => Number.isFinite(h) && h >= 0 && h < 50);
  for (const h of [...new Set(holes)]) if (h !== spill) fabricRow(shape, h, speed, 1);  // best hole
  fabricRow(shape, spill, speed, 0, true);                                             // spares of the default
}
function renderFabric(d) { fabricShapes = d.shapes; fabricMatrix(); }
$("fab-add").addEventListener("click", () => fabricRow(form.elements.shape.value, form.elements.spill.value, form.elements.speed.value));
$("fab-matrix").addEventListener("click", fabricMatrix);
$("fab-clear").addEventListener("click", () => { $("fab-designs").innerHTML = ""; });
$("fab-designs").addEventListener("click", (e) => { if (e.target.classList.contains("fab-del")) e.target.closest("tr").remove(); });
$("fab-run").addEventListener("click", () => {
  if (!workerReady || !form.checkValidity()) { form.reportValidity(); return; }
  const designs = [...$("fab-designs").children].map((tr) => {
    const v = (f) => tr.querySelector(`[data-f="${f}"]`);
    return { shape: v("shape").value, spill: Number(v("spill").value), speed: Number(v("speed").value),
             qty: Number(v("qty").value), fill: v("fill").checked };
  });
  if (!designs.length) { $("fab-status").textContent = "Add at least one design."; return; }
  $("fab-run").disabled = true;
  $("fab-run").textContent = "Building layout…";
  $("fab-status").textContent = "Packing the pieces and drawing the A4 pages – this can take up to a minute.";
  worker.postMessage({ kind: "layout", params: params(), layout: {
    width_mm: Number($("fab-w").value), length_mm: Number($("fab-l").value), gap_mm: Number($("fab-gap").value), designs } });
});
function showFabric(r) {
  fabricUrls.forEach((u) => URL.revokeObjectURL(u));
  const url = (blob) => { const u = URL.createObjectURL(blob); fabricUrls = [...fabricUrls, u]; return u; };
  fabricUrls = [];
  const pdfBytes = Uint8Array.from(atob(r.pdf), (c) => c.charCodeAt(0));
  const svgUrl = url(new Blob([r.svg], { type: "image/svg+xml" }));
  const pct = (100 * r.used_m2 / r.fabric_m2).toFixed(0);
  $("fab-stats").innerHTML = `<p><strong>${pct} % of the fabric used</strong> (${fmt(r.used_m2, 2)} of ${fmt(r.fabric_m2, 2)} m², including seam allowances) · ${r.pages} A4 pages (${r.rows} rows × ${r.cols} columns)</p><ul>` +
    r.designs.map((d) => `<li>${esc(d.label)} – <strong>${d.count}</strong> parachute${d.count === 1 ? "" : "s"}${d.pieces > 1 ? ` (${d.pieces} gores each)` : ""}</li>`).join("") + "</ul>" +
    r.unplaced.map((u) => `<p class="notice">${esc(u.label)}: ${u.missing} cop${u.missing === 1 ? "y" : "ies"} did not fit.</p>`).join("");
  $("fab-preview").innerHTML = `<img alt="Layout of all canopy pieces on the fabric" src="${svgUrl}">`;
  const tplBytes = Uint8Array.from(atob(r.templates_pdf), (c) => c.charCodeAt(0));
  $("fab-downloads").innerHTML =
    `<a class="btn" download="asteria-parachute-templates.pdf" href="${url(new Blob([tplBytes], { type: "application/pdf" }))}">Reusable templates + cutting map (PDF, ${r.template_pages} pages)</a>` +
    `<a class="btn secondary" download="asteria-fabric-A4-pages.pdf" href="${url(new Blob([pdfBytes], { type: "application/pdf" }))}">Whole layout full size (PDF, ${r.pages + 1} pages)</a>` +
    `<a class="btn" download="asteria-fabric-layout.svg" href="${svgUrl}">Full-size layout (SVG)</a>` +
    `<a class="btn" download="asteria-drop-test-sheet.csv" href="${url(new Blob([testSheet(r)], { type: "text/csv" }))}">Drop-test record sheet (CSV)</a>`;
  $("fab-result").hidden = false;
  $("fab-status").textContent = "";
}

function testSheet(r) {
  const q = (v) => /[",\n]/.test(String(v)) ? `"${String(v).replace(/"/g, '""')}"` : String(v);
  const rows = [["Canopy", "Shape", "Spill hole %", "Width cm", "Area m2", "Predicted speed m/s",
                 "Drop height m", "Fall time s", "Measured speed m/s", "Max swing deg", "Settles below 5 deg after s", "Notes"]];
  for (const d of r.designs) for (let i = 1; i <= d.count; i++)
    rows.push([d.code + i, d.shape, d.spill, d.width_cm.toFixed(1), d.area_m2.toFixed(4), d.speed, "", "", "", "", "", ""]);
  return "\ufeff" + rows.map((x) => x.map(q).join(",")).join("\r\n");
}
