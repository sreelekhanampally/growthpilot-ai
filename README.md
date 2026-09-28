# GrowthPilot AI

### Sales & Customer Intelligence Copilot

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-API-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-Vite-61DAFB?logo=react&logoColor=black)](https://react.dev/)
[![Tests](https://img.shields.io/badge/backend_tests-52_passed-brightgreen)](#verification)
[![Live](https://img.shields.io/badge/Render-live-46E3B7?logo=render&logoColor=black)](https://growthpilot-web.onrender.com)

**[Live application](https://growthpilot-web.onrender.com)** ·
**[API documentation](https://growthpilot-api-78dt.onrender.com/docs)** ·
**[API health](https://growthpilot-api-78dt.onrender.com/health)**

GrowthPilot is an end-to-end AI decision-support platform for retail SMEs. It converts raw
transactions into customer segments, churn and purchase-propensity scores, ranked product
recommendations, next-best actions, and grounded Copilot answers.

The product is built around one practical loop:

> Transactions → customer state → predictions → recommended action → grounded explanation → human decision

It is not a generic chatbot attached to a dashboard. Structured questions are answered from
approved analytics functions and Customer 360 data; playbook questions use retrieval; every
answer includes its route, evidence, confidence, and agent trace.

## Live demo snapshot

The deployed demonstration is reproducibly generated from the repository's synthetic retail
dataset.

| Signal | Live demo value |
| --- | ---: |
| Transaction rows | 13,981 |
| Customers | 240 |
| Leakage-safe training snapshots | 3,325 |
| Lifetime revenue | £865,258 |
| Customers at high churn risk | 68 |
| Ranked sales opportunities | 92 |
| Backend tests | 52 passed |

These values describe the synthetic demo environment. They are not presented as real-world model
performance or business impact.

## Questions GrowthPilot can answer

- How many customers do we have?
- Which customers should the sales team contact today?
- Why is Customer 15000 at risk?
- Recommend products for a specific customer.
- Which segment generated the most value?
- Which customers have high purchase intent?
- What are the best practices in our retention playbook?
- What action should we take for high-value churn-risk customers?

## Product capabilities

| Capability | What it does |
| --- | --- |
| Data foundation | Downloads or generates retail data, validates rows, separates returns, reconciles totals, and produces EDA |
| Customer feature pipeline | Builds RFM, behavioral windows, basket, return, trend, tenure, and purchase-interval features at historical cutoffs |
| Segmentation | Selects and validates K-Means clusters, then maps them to business-readable customer groups |
| Churn prediction | Estimates whether a customer will make no purchase during the next 90 days |
| Purchase propensity | Estimates whether a customer will purchase during the next 30 days |
| Recommendations | Combines item-item, segment-affinity, and popularity signals with cold-start handling |
| Decision engine | Combines value, segment, risk, intent, and product ranking into a prioritized next-best action |
| Customer 360 | Brings features, model scores, explanations, recommendations, and actions into one profile |
| Multi-agent Copilot | Routes each question to safe SQL analytics, Customer 360, RAG, or a hybrid workflow |
| Grounding and safety | Validates factual claims, attaches citations, records traces, and falls back deterministically |

## Architecture

~~~mermaid
flowchart TB
    A["Retail transactions"] --> B["Cleaning and quality gates"]
    B --> C["SQL database"]
    C --> D["Temporal feature snapshots"]
    D --> E["Segments and predictive models"]
    C --> F["Recommendation engine"]
    E --> G["Next-best-action engine"]
    F --> G
    G --> H["FastAPI intelligence layer"]
    I["Approved playbooks"] --> J["Multi-agent Copilot"]
    H --> J
    H --> K["React analytics app"]
    J --> K
~~~

GrowthPilot is intentionally a modular monolith. Offline pipelines own training and evaluation;
the online FastAPI application owns stable analytics, inference, recommendation, and Copilot
contracts. Structured business facts stay in SQL instead of being embedded and handed to an LLM.

## Multi-agent Copilot

~~~mermaid
flowchart TD
    Q["User question"] --> S["Supervisor"]
    S --> A["Analytics agent"]
    S --> C["Customer Intelligence agent"]
    S --> R["Retrieval agent"]
    A --> Y["Reasoning agent"]
    C --> Y
    R --> Y
    Y --> V["Grounding validator"]
    V --> O["Answer, sources, confidence, trace"]
~~~

The supervisor applies deterministic routing for known intents and bounded model routing for
unknown intents. Specialists can call only approved functions:

- **Analytics agent:** allow-listed customer, revenue, segment, churn, and opportunity metrics
- **Customer Intelligence agent:** Customer 360, model scores, ranked products, and next action
- **Retrieval agent:** approved retention and growth playbook chunks
- **Reasoning agent:** concise synthesis from supplied evidence only
- **Validator agent:** grounding checks with a single repair pass and safe fallback

The application works without an external model. Optional Gemini and Ollama adapters improve
language synthesis while deterministic routing, evidence collection, validation, and fallback
remain available.

## ML design

- **Churn label:** no purchase in the interval (T, T + 90 days]
- **Propensity label:** at least one purchase in (T, T + 30 days]
- **Leakage control:** every feature uses transactions at or before cutoff T
- **Temporal evaluation:** earlier snapshots train, later snapshots validate, latest snapshots test
- **Model metrics:** F1, precision, recall, ROC-AUC, PR-AUC, calibration, and confusion matrices
- **Segmentation checks:** silhouette quality, cluster size, repeated-seed stability, and interpretability
- **Recommendation checks:** Precision@K, Recall@K, NDCG@K, and leave-last-order-out evaluation

The lightweight installation uses scikit-learn gradient boosting. The optional ML installation
adds XGBoost and SHAP. Artifacts retain feature names, thresholds, versions, training bounds,
parameters, and evaluation metadata.

## Technology stack

| Layer | Technology |
| --- | --- |
| Data and ML | Pandas, NumPy, scikit-learn, optional XGBoost and SHAP |
| Backend | FastAPI, Pydantic, SQLAlchemy, Alembic |
| Database | PostgreSQL for the full stack; SQLite for the reproducible demo |
| RAG and LLM | approved retrieval, optional Sentence Transformers/pgvector, Gemini, Ollama |
| Frontend | React, TypeScript, Vite, TanStack Query, React Router, Recharts |
| Delivery | Docker Compose, Render, GitHub Actions, pytest, Ruff |

## Quick start

### Windows

Use Python 3.11+ and Node.js 20+ from the repository root:

~~~powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\setup_demo.ps1
python -m growthpilot serve
~~~

Open a second terminal:

~~~powershell
cd frontend
npm install
npm run dev
~~~

Open http://localhost:5173. FastAPI documentation is available at
http://localhost:8000/docs.

### macOS or Linux

~~~bash
chmod +x scripts/setup_demo.sh
./scripts/setup_demo.sh
python -m growthpilot serve
~~~

In a second terminal:

~~~bash
cd frontend
npm install
npm run dev
~~~

The setup command generates the synthetic dataset, runs cleaning and quality checks, applies
migrations, loads the database, builds the current feature snapshot, trains all models, scores
customers, and generates recommendations.

## Copilot providers

GrowthPilot defaults to deterministic mode, so the entire product remains usable without a paid
API or local model.

Copy .env.example to .env and choose one provider:

~~~dotenv
# No external model
LLM_PROVIDER=deterministic

# Gemini with deterministic fallback
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_new_key
GEMINI_MODEL=gemini-2.5-flash

# Local Ollama with deterministic fallback
LLM_PROVIDER=ollama
OLLAMA_ENABLED=true
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:3b

# Ollama/Gemini failover followed by deterministic fallback
LLM_PROVIDER=hybrid
HYBRID_PRIMARY=ollama
~~~

Never commit .env, model binaries, databases, downloaded workbooks, or API keys.

## Full UCI pipeline

The original Online Retail II workbook is downloaded from its publisher and intentionally not
committed.

~~~bash
python -m growthpilot download
python -m growthpilot phase1 --input data/raw/online_retail_II.xlsx
python -m growthpilot db-upgrade
python -m growthpilot load-db
python -m growthpilot build-features --as-of "2011-12-09T12:50:00"
python -m growthpilot train-all
~~~

The repository includes data/demo/demo_transactions.csv for the complete walkthrough and
data/sample/online_retail_sample.csv for edge-case tests.

## Useful CLI commands

| Command | Result |
| --- | --- |
| growthpilot setup-demo | Creates or recovers the complete local demo |
| growthpilot download | Downloads and validates Online Retail II |
| growthpilot phase1 | Runs cleaning, rejection logging, quality gates, and EDA |
| growthpilot db-upgrade | Applies the Alembic schema |
| growthpilot load-db | Loads canonical transactions idempotently |
| growthpilot build-features | Builds a cutoff-safe customer snapshot |
| growthpilot train-all | Trains, evaluates, persists, and scores every model |
| growthpilot serve | Starts the FastAPI application |

On Windows, python -m growthpilot is the most reliable form when the virtual environment is
active.

## API surface

| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET | /health | Service and Copilot-provider status |
| GET | /api/v1/dashboard/summary | Executive metrics |
| GET | /api/v1/customers | Searchable customer directory |
| GET | /api/v1/customers/{id} | Customer 360 |
| GET | /api/v1/segments | Segment profiles |
| GET | /api/v1/opportunities | Ranked sales opportunities |
| GET | /api/v1/models/performance | Approved model metrics |
| POST | /api/v1/copilot/chat | Grounded multi-agent answer |
| POST | /api/v1/actions | Record a human action |
| PATCH | /api/v1/actions/{id} | Record the outcome |

See [docs/API.md](docs/API.md) for request and response contracts.

## Repository structure

~~~text
growthpilot-ai/
├── frontend/                   React analytics application
├── src/growthpilot/
│   ├── agents/                 supervisor, specialists, LLM failover, validator
│   ├── api/                    FastAPI routes and schemas
│   ├── data/                   ingestion, cleaning, quality, and EDA
│   ├── db/                     SQLAlchemy models, migrations, and loading
│   ├── features/               leakage-safe customer features
│   ├── ml/                     snapshots, segmentation, and supervised models
│   ├── recommendations/        hybrid product ranking
│   ├── decision/               next-best-action policy
│   ├── rag/                    chunking, retrieval, and grounded Copilot
│   └── services/               customer-intelligence queries
├── migrations/                 Alembic schema history
├── data/demo/                  reproducible synthetic demo
├── tests/                      unit and integration tests
├── docs/                       product, architecture, API, and phase documents
├── scripts/                    Bash and PowerShell setup
├── render.yaml                 Render deployment blueprint
├── docker-compose.yml
└── .github/workflows/ci.yml
~~~

## Verification

~~~bash
python -m ruff check src tests
python -m pytest
cd frontend && npm ci && npm run build
~~~

Current verified state:

- 52 backend tests passed
- Ruff passed
- React/TypeScript production build passed
- fresh database migration and demo bootstrap passed
- live dashboard, SQL analytics, Customer 360, and RAG Copilot checks passed
- Render frontend and API health checks returned HTTP 200

## Deployment notes

The public Render deployment uses the isolated SQLite demo mode and automatically reconstructs
its database and model artifacts after a fresh deployment. This keeps the portfolio demo
self-contained, but action history can be reset when Render replaces the instance.

For persistent production data, configure a dedicated PostgreSQL DATABASE_URL and run Alembic
migrations before serving. Local Ollama cannot be reached from Render; use deterministic mode or a
cloud provider such as Gemini for deployed model synthesis.

## Documentation

- [Product requirements](docs/PHASE_0_PRD.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Data contract](docs/DATA_CONTRACT.md)
- [Database](docs/PHASE_2_DATABASE.md)
- [Customer features](docs/PHASE_3_FEATURES.md)
- [Phases 4–20](docs/PHASES_4_20.md)
- [Multi-agent Copilot](docs/MULTI_AGENT_COPILOT.md)
- [Deployment](docs/DEPLOYMENT.md)
- [GitHub checklist](docs/GITHUB_CHECKLIST.md)

## Scope and responsible use

GrowthPilot is a portfolio-grade decision-support product, not an autonomous customer-contact
system. Customer-facing actions require human approval. A production version should add
authentication, tenant isolation, scheduled jobs, monitoring, drift checks, causal campaign
evaluation, privacy controls, and dedicated persistent infrastructure.

Online Retail II remains subject to its publisher's citation and usage terms. The bundled demo
data is synthetic.
