# API reference

Interactive OpenAPI documentation is available at `/docs` while the API runs.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health` | Liveness and version |
| GET | `/api/v1/dashboard/summary` | Executive KPIs and segment counts |
| GET | `/api/v1/customers` | Paginated customer directory |
| GET | `/api/v1/customers/{id}` | Customer 360, scores, products, next action |
| GET | `/api/v1/segments` | Business segment summary |
| GET | `/api/v1/opportunities` | Customers ranked by purchase propensity |
| GET | `/api/v1/models/performance` | Versioned model evaluation |
| POST | `/api/v1/actions` | Log a recommended or manual action |
| PATCH | `/api/v1/actions/{id}` | Record completion and outcome |
| POST | `/api/v1/copilot/chat` | Multi-agent grounded question answering |

All endpoints are workspace-scoped through `WORKSPACE_SLUG`. Authentication is intentionally outside the local portfolio MVP; add an identity provider and workspace membership checks before a multi-tenant production launch.

The Copilot response preserves the earlier `answer`, `intent`, `citations`, and `data` fields and
adds:

- `route`: selected specialist path;
- `trace`: ordered supervisor/specialist/reasoning/validation events;
- `validation`: grounding result, confidence, notes, and unsupported claims;
- `provider`: `deterministic`, `gemini`, `ollama`, or a repair fallback.

`GET /health` also reports `copilot: multi_agent` and the configured provider chain.
