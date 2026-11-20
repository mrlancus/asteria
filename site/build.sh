#!/usr/bin/env bash
# Portable static-site build; run from the repository root.
set -euo pipefail
python3 "$(dirname "$0")/build.py"
