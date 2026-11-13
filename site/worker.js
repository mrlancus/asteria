// Runs the real cansat_design Python package in the browser with Pyodide.
// Keep PY_FILES in sync with the files in cansat_design/.
importScripts("https://cdn.jsdelivr.net/pyodide/v0.26.4/full/pyodide.js");

const PY_FILES = ["__init__.py", "__main__.py", "atmosphere.py", "config.py", "descent.py",
  "design.py", "mass.py", "parachute.py", "plots.py", "svg_export.py", "sweeps.py"];

let py = null;

async function init() {
  py = await loadPyodide();
  postMessage({ type: "status", text: "Loading numpy, scipy and matplotlib…" });
  await py.loadPackage(["numpy", "scipy", "matplotlib"]);
  postMessage({ type: "status", text: "Loading the calculator…" });
  py.FS.mkdirTree("/home/pyodide/cansat_design");
  for (const f of PY_FILES) {
    const r = await fetch("cansat_design/" + f);
    if (!r.ok) throw new Error("Could not load cansat_design/" + f);
    py.FS.writeFile("/home/pyodide/cansat_design/" + f, await r.text());
  }
  py.FS.writeFile("/home/pyodide/web_api.py", await (await fetch("web_api.py")).text());
  await py.runPythonAsync("import sys; sys.path.insert(0, '/home/pyodide'); import web_api");
  postMessage({ type: "ready", defaults: JSON.parse(py.runPython("web_api.defaults_json()")) });
}

onmessage = async (e) => {
  try {
    py.globals.set("params_json", JSON.stringify(e.data.params));
    py.globals.set("with_sweeps", e.data.sweeps);
    const out = py.runPython("web_api.run(params_json, with_sweeps)");
    postMessage({ type: "result", result: JSON.parse(out) });
  } catch (err) {
    postMessage({ type: "error", text: String(err) });
  }
};

init().catch((err) => postMessage({ type: "error", text: String(err) }));
