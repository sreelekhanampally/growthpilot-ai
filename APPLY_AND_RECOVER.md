# GrowthPilot missing-database recovery fix

Prepared against GitHub commit:

`c08cd52f720a08eea87f10955ab9d53267ea9cb2`

## Why the app failed

The React message `Could not load data: Failed to fetch` means the FastAPI backend was unreachable.
The deleted file was almost certainly `growthpilot.db`. That file is generated runtime data and is
intentionally ignored by Git, so it cannot be restored with `git pull`.

## Apply the changed files

1. Extract this ZIP.
2. Copy all extracted folders and files into the root of your `growthpilot-ai` repository.
3. Allow Windows to merge folders and replace matching files.
4. Do not add or commit `growthpilot.db`; `.gitignore` excludes it intentionally.

## Recover the database on Windows

Open PowerShell in the repository root:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m growthpilot setup-demo
python -m growthpilot serve
```

Wait until the backend reports:

```text
Uvicorn running on http://0.0.0.0:8000
```

Keep that terminal open. In a second PowerShell terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173` and hard-refresh with `Ctrl+F5`.

## Expected recovery result

The tracked demo dataset rebuilds:

- 13,981 transaction rows
- 240 customers
- 3,325 historical training snapshots
- segmentation, churn, propensity, and recommendation outputs

Test the Copilot with:

`How many customers do we have?`

Expected answer:

`GrowthPilot currently has 240 customers.`

## Verification performed

- 42 backend tests passed
- Ruff passed
- React/TypeScript production build passed
- Missing database detection passed without creating an empty database
- Fresh database recovery passed
- Re-running recovery was idempotent
- Dashboard and Copilot API smoke tests passed

