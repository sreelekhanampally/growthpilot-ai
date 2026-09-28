# Phases 4–20 implementation

## Phase 4 — segmentation

`growthpilot.ml.segmentation` log-transforms skewed customer measures, scales them with `RobustScaler`, evaluates K=3…8 with silhouette score and repeated-seed adjusted Rand stability, selects the best combined score, and assigns business-readable names. Assignments and run metadata are versioned in the database.

## Phases 5–7 — temporal labels and predictive models

Historical monthly cutoffs generate features using information available at each cutoff. Churn means no purchase in the following 90 days. Propensity means at least one purchase in the following 30 days. Dates are split chronologically into train, validation, and test partitions; the validation set selects the F1 threshold and the untouched test set reports F1, precision, recall, ROC-AUC, PR-AUC, and a confusion matrix.

The default lightweight install uses scikit-learn histogram gradient boosting. Installing `.[full]` activates XGBoost automatically. This fallback keeps the demo portable without changing the model contract.

## Phase 8 — recommendations

The hybrid recommender combines item-item cosine similarity, catalog popularity, and segment popularity. Previously purchased products are excluded. Leave-last-order-out evaluation reports Hit Rate@K and MRR@K.

## Phase 9 — next best action

The deterministic policy combines customer value, segment, churn probability, propensity, and the first recommended product. It returns retention, cross-sell, reactivation, or nurture actions with a 0–100 priority score and rationale.

## Phases 10–12 — API, dashboard, and Customer 360

FastAPI exposes dashboard, customers, segments, opportunities, model performance, actions, and copilot endpoints. The React/Vite app consumes these endpoints with TanStack Query and renders an executive dashboard, customer directory, Customer 360, segment cards, opportunity queue, copilot, and model-health pages.

## Phases 13–14 — embeddings and copilot

Knowledge is split into overlapping chunks. `all-MiniLM-L6-v2` provides 384-dimensional embeddings when the model is locally available. A deterministic normalized hashing embedder supports offline development. PostgreSQL deployments can replace the JSON development column with pgvector while preserving the retrieval service interface.

The copilot routes metric questions to structured analytics, customer questions to Customer 360, and strategy questions to the knowledge retriever. It never asks an LLM to calculate transaction metrics.

## Phase 15 — explanations

Each predictive run stores global feature importance. XGBoost exposes native gain importance; the lightweight estimator uses permutation importance. Customer scores store the approved run's leading drivers. SHAP is included in the full dependency set for production-grade local explanations.

## Phase 16 — action feedback

Recommended actions have status, outcome, completion time, and attributable outcome value. These records form the future policy-learning dataset without contaminating current supervised labels.

## Phases 17–20 — quality and delivery

The repository contains unit/integration tests, Ruff linting, GitHub Actions, Docker images, Docker Compose with PostgreSQL/pgvector, a Render blueprint, data and model contracts, model metadata, the architecture document, and one-command demo setup scripts for PowerShell and Bash.

## Honest model-evaluation note

The included demo data is synthetic and exists to prove the engineering path. Its metrics are not evidence of real-world business performance. Run `growthpilot download` and repeat the temporal pipeline on UCI Online Retail II for portfolio metrics, and label any claims with the dataset and test cutoff used.
