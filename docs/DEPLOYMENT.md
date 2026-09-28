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

`deploy/render.yaml` defines PostgreSQL, the Docker API, and the static React app. Set `CORS_ORIGINS` to the frontend URL and `VITE_API_URL` to the API URL. Apply migrations as a release/pre-deploy command before serving traffic. Free plans and availability vary; review current provider settings before deployment.

## Production checklist

- Replace demo credentials and restrict CORS.
- Add authentication and workspace authorization.
- Use managed PostgreSQL backups and TLS.
- Store model artifacts in versioned object storage.
- Configure an LLM provider only through server-side secrets.
- Add job scheduling for feature builds, retraining, scoring, and drift checks.
- Pin the approved model version instead of auto-approving every training run.
- Monitor latency, API errors, model score distributions, action conversion, and data freshness.
