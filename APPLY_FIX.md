# GrowthPilot Copilot SQL + stale-response fix

This patch was prepared against repository commit:

`468cffab94f8462cecb1a120896af618093dfcc4`

## What it fixes

- `How many customers do we have?` now returns the customer count instead of the revenue answer.
- Propensity and purchase-intent questions use the sales-opportunity query.
- Unsupported analytics questions no longer silently default to revenue.
- The previous Copilot answer is cleared while a new question is running.
- Suggested prompt buttons now submit their question immediately.
- Copilot POST requests opt out of browser caching.

## Apply on Windows

1. Extract this ZIP.
2. Copy every extracted folder into the root of your `growthpilot-ai` repository.
3. Allow Windows to merge folders and replace the matching files.
4. Do not copy any `.env` file; this patch intentionally does not contain one.

Then open PowerShell in the repository root:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m pytest
python -m ruff check .
```

Validate the frontend:

```powershell
cd frontend
npm ci
npm run build
cd ..
```

Start the application:

```powershell
python -m growthpilot serve
```

In a second terminal:

```powershell
cd frontend
npm run dev
```

Open `http://localhost:5173`, hard-refresh once with `Ctrl+F5`, and test:

1. `What is our total revenue?`
2. `How many customers do we have?`

The second answer should report only the current customer count. With the bundled demo dataset it is:

`GrowthPilot currently has 240 customers.`

## Verification performed

- Python tests: 40 passed
- Ruff: passed
- React/TypeScript production build: passed
- Fresh demo pipeline: 13,981 rows loaded; 240 customers; 3,325 training snapshots
- Live FastAPI Copilot smoke tests: revenue, customer count, segments, opportunities, hybrid RAG, and Customer 360 passed

