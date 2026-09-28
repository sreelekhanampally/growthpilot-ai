#!/usr/bin/env bash
set -euo pipefail

python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
export DATABASE_URL='sqlite+pysqlite:///growthpilot.db'
python -m growthpilot demo-data
python -m growthpilot phase1 --input data/demo/demo_transactions.csv
python -m growthpilot db-upgrade
python -m growthpilot load-db
python -m growthpilot build-features --as-of '2011-12-09T23:59:59'
python -m growthpilot train-all
echo 'Demo ready. Run python -m growthpilot serve, then npm install && npm run dev in frontend/.'
