// Page logic: collects the inputs, sends them to the Python worker and shows the results.
const $ = (id) => document.getElementById(id);
const form = $("form");
const worker = new Worker("worker.js");
let components = [];

const fmt = (x, d = 1) => Number(x).toFixed(d);
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

function fillDefaults(d) {
  $("shape").innerHTML = Object.entries(d.shapes)
    .map(([k, v]) => `<option value="${k}">${esc(v)}</option>`).join("");
  for (const k of ["shape", "mass_g", "speed", "spill", "apogee", "opening_speed", "fabric_g_m2", "seam_mm", "line_factor", "density"]) {
    form.elements[k].value = d[k];
  }
  components = d.components;
  $("comps").innerHTML = components.map((c, i) => `
    <tr><td>${esc(c.name)}</td>
    <td><input type="number" step="0.1" min="0" data-i="${i}" data-k="mass_g" value="${c.mass_g}" aria-label="${esc(c.name)} mass"></td>
    <td><input type="number" step="1" min="0" data-i="${i}" data-k="qty" value="${c.qty}" aria-label="${esc(c.name)} quantity"></td>
    <td><input type="checkbox" data-i="${i}" data-k="estimate" ${c.estimate ? "checked" : ""} aria-label="${esc(c.name)} is an estimate"></td></tr>`).join("");
}

function params() {
  const p = Object.fromEntries(new FormData(form).entries());
  for (const el of $("comps").querySelectorAll("input")) {
    const c = components[el.dataset.i];
    c[el.dataset.k] = el.type === "checkbox" ? el.checked : Number(el.value);
  }
  p.components = components;
  return p;
}

function run() {
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
  ].map(([t, v, s, st]) => `<div class="tile"><div class="t">${t}</div><div class="v">${v}</div><div class="s">${s}${st ? ` <span class="badge ${st}">${STATUS_ICON[st]} ${st}</span>` : ""}</div></div>`).join("");

  $("checks").innerHTML = r.checks.map((c) =>
    `<tr><td><span class="badge ${c.status}">${STATUS_ICON[c.status]} ${c.status}</span></td><td>${esc(c.rule)}</td><td class="val">${esc(c.value)}</td></tr>`).join("");

  $("shapes").innerHTML = r.shapes.map((s) =>
    `<tr class="${s.chosen ? "chosen" : ""}"><td>${esc(s.shape)}${s.chosen ? " ★" : ""}</td><td>${fmt(s.cd0, 2)}</td><td>${fmt(s.area_m2, 4)}</td>
     <td>${fmt(s.width_cm)}</td><td>${fmt(s.hole_cm)}</td><td>${fmt(s.mass_g)}</td><td class="dims">${esc(s.dims)}</td></tr>`).join("");

  const svgUrl = (text) => URL.createObjectURL(new Blob([text], { type: "image/svg+xml" }));
  const names = Object.keys(r.svgs);
  $("pattern").innerHTML = `<img alt="Canopy cutting pattern" src="${svgUrl(r.svgs["canopy_pattern.svg"])}">`;
  $("downloads").innerHTML = names.map((n) =>
    `<a class="btn" download="${n}" href="${svgUrl(r.svgs[n])}">${n === "canopy_pattern.svg" ? "Full-size SVG" : n.replace("canopy_", "").replace(".svg", "")}</a>`).join("");

  const img = (key, alt) => r.images[key] ? `<img alt="${alt}" src="data:image/png;base64,${r.images[key]}">` : "";
  $("plot-descent").innerHTML = img("descent", "Altitude, speed and swing angle against time");
  $("plot-sweeps").innerHTML = img("speed_vs_area", "Descent speed against canopy area for each shape")
    + img("speed_vs_mass", "Descent speed against flight mass") + img("swing_vs_spill", "Swing settle time and canopy width against spill-hole size");
  $("sweep-panel").hidden = !r.images.speed_vs_area;
  $("summary").textContent = r.summary;
}

worker.onmessage = (e) => {
  const m = e.data;
  if (m.type === "status") $("status").textContent = m.text;
  if (m.type === "ready") { fillDefaults(m.defaults); run(); }
  if (m.type === "result") show(m.result);
  if (m.type === "error") $("status").textContent = "Error: " + m.text;
  if (m.type === "result" || m.type === "error") {
    $("run").disabled = false;
    $("run").textContent = "Calculate";
    document.body.classList.remove("busy");
  }
};

form.addEventListener("submit", (e) => { e.preventDefault(); run(); });
