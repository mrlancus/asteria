#!/usr/bin/env bash
# Builds the static website into dist/ (used by Cloudflare Pages and for local testing).
# Run from the repo root: bash site/build.sh   then   python3 -m http.server -d dist
set -euo pipefail
rm -rf dist
mkdir -p dist/cansat_design
cp site/index.html site/style.css site/app.js site/worker.js site/web_api.py dist/
cp cansat_design/*.py dist/cansat_design/
echo "Built dist/"
