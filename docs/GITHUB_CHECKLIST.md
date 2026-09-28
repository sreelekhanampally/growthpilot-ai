# GitHub publishing checklist

1. Extract the ZIP and open a terminal in `growthpilot-ai`.
2. Confirm `.env` and local databases are absent: `git status --ignored`.
3. Run `python -m pytest` and `python -m ruff check .`.
4. Build the UI with `cd frontend && npm ci && npm run build`.
5. Initialize and push:

```bash
git init
git add .
git commit -m "Build GrowthPilot AI end-to-end"
git branch -M main
git remote add origin YOUR_REPOSITORY_URL
git push -u origin main
```

The full UCI workbook, generated processed data, local databases, secrets, caches, and runtime model binaries are ignored. The repository includes the synthetic demo CSV, reproducible dataset downloader, training code, model metadata, tests, and all configuration required to regenerate outputs.
