$ErrorActionPreference = "Stop"

if (-not (Test-Path ".venv")) { py -3.11 -m venv .venv }
& .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
$env:DATABASE_URL = "sqlite+pysqlite:///growthpilot.db"

python -m growthpilot demo-data
python -m growthpilot phase1 --input data/demo/demo_transactions.csv
python -m growthpilot db-upgrade
python -m growthpilot load-db
python -m growthpilot build-features --as-of "2011-12-09T23:59:59"
python -m growthpilot train-all

Write-Host "Demo ready. Run: python -m growthpilot serve"
Write-Host "In another terminal: cd frontend; npm install; npm run dev"
