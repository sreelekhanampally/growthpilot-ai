# Deployment

## Local Docker

```bash
docker compose up --build -d db
docker compose run --rm api python -m growthpilot db-upgrade
docker compose up --build api frontend
```

Open the UI at `http://localhost:5173`, API docs at `http://localhost:8000/docs`, and health endpoint at `http://localhost:8000/health`.

Load data and train through one-off API containers after the database is healthy. The `data/` and `artifacts/` directories are mounted for this purpose.

## Render

The repository-root `render.yaml` defines a free PostgreSQL database, the Python API, and
the static React site in the Singapore region. The API start command uses
`--bootstrap-demo`: it migrates and populates an empty database once, then skips the
bootstrap on normal restarts.

Set `CORS_ORIGINS` to the deployed frontend URL and `VITE_API_URL` to the deployed API
URL. A computer-local Ollama server is not reachable from Render; use deterministic mode
or configure a newly generated `GEMINI_API_KEY` as a server-side secret. Never commit the
key. Free database availability and expiration policies can change, so review the active
resource in the Render dashboard.

## Production checklist

- Replace demo credentials and restrict CORS.
- Add authentication and workspace authorization.
- Use managed PostgreSQL backups and TLS.
- Store model artifacts in versioned object storage.
- Configure an LLM provider only through server-side secrets.
- Add job scheduling for feature builds, retraining, scoring, and drift checks.
- Pin the approved model version instead of auto-approving every training run.
- Monitor latency, API errors, model score distributions, action conversion, and data freshness.
