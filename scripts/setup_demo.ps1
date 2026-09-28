$ErrorActionPreference = "Stop"

if (-not (Test-Path ".venv")) { py -3.11 -m venv .venv }
& .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m growthpilot setup-demo

Write-Host "Demo ready. Run: python -m growthpilot serve"
Write-Host "In another terminal: cd frontend; npm install; npm run dev"
