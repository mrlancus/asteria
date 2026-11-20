"""Build the static site using only the standard library on Windows/macOS/Linux."""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from cansat_design.sourcing import parts_catalog

out = ROOT / "dist"
package = out / "cansat_design"
package.mkdir(parents=True, exist_ok=True)
for name in ("index.html", "style.css", "app.js", "parts.js", "worker.js", "web_api.py"):
    shutil.copyfile(ROOT / "site" / name, out / name)
files = sorted((ROOT / "cansat_design").glob("*.py"))
for path in files:
    shutil.copyfile(path, package / path.name)
(package / "files.json").write_text(json.dumps([p.name for p in files]), encoding="utf-8")
(out / "parts.json").write_text(json.dumps(parts_catalog(), ensure_ascii=False, indent=2), encoding="utf-8")
print("Built dist/")
