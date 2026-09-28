#!/usr/bin/env bash
set -euo pipefail

if [[ ! -d .venv ]]; then python3 -m venv .venv; fi
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
python -m growthpilot setup-demo
echo 'Demo ready. Run python -m growthpilot serve, then npm install && npm run dev in frontend/.'
