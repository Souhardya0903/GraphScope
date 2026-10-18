#!/usr/bin/env sh
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
if [ ! -x .venv/bin/python ]; then "${PYTHON:-python3}" -m venv .venv; fi
.venv/bin/python -m pip install -e ".[dev]"
npm ci --prefix tools/javascript --ignore-scripts
npm ci --prefix frontend --ignore-scripts
npm --prefix frontend run build
.venv/bin/python -m graphscope doctor
