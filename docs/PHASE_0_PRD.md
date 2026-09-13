# Phase 0 Product Requirements Document

## 1. Product definition

**GrowthPilot AI** is a decision-support application that helps a retail SME decide whom to contact, what action to take, and why. It joins customer analytics, predictive models, recommendations, and grounded AI explanations in one workflow.

The product is not an autonomous sales agent. A human user reviews and performs every suggested commercial action.

## 2. Target user and job to be done

### Primary persona

An owner, growth manager, or small sales team at an e-commerce/transactional retail business that has order data but lacks a dedicated data-science team.

### Core job

> When I begin my workday, help me identify the highest-value customer opportunities and risks, explain the evidence, and record what action I took.

## 3. Problem statement

Transaction exports contain useful behavioral signals, but SME teams normally inspect backward-looking totals. They cannot reliably prioritize customers who are likely to churn, likely to buy, or suitable for a particular product. Generic chat over raw transaction rows is neither accurate nor auditable.

## 4. Product loop

1. Import historical transactions.
2. Build a time-valid customer state.
3. Estimate segment, churn risk, and purchase propensity.
4. Rank candidate products and commercial opportunities.
5. Produce a rule-governed next best action.
6. Explain the action from structured facts and approved playbooks.
7. Capture the user's action and eventual result for later evaluation.

## 5. MVP functional requirements

| ID | Requirement | Acceptance criterion |
| --- | --- | --- |
| FR-01 | Import transactions | Valid UCI-format Excel/CSV files are normalized without manual column editing. |
| FR-02 | Show data quality | Every input row reconciles to purchase, return, or rejected output; rejection reasons are counted. |
| FR-03 | Customer 360 | User can see value, recency, frequency, predictions, explanations, recommendations, and recent orders for one customer. |
| FR-04 | Segmentation | Customers receive stable business-readable behavioral segments backed by measured cluster quality. |
| FR-05 | Churn risk | Score predicts no purchase in a future 90-day window from information available at a historical cutoff. |
| FR-06 | Purchase propensity | Score predicts at least one purchase in a future 30-day window from cutoff-valid features. |
| FR-07 | Recommendations | Existing and cold-start customers receive ranked products with offline ranking metrics. |
| FR-08 | Next best action | A deterministic policy combines value, segment, churn, propensity, and product signals into a suggested action. |
| FR-09 | Grounded copilot | Quantitative answers come from structured functions; strategy answers cite retrieved approved knowledge. |
| FR-10 | Feedback | User can accept, reject, or complete an action and optionally record outcome/value. |

## 6. Phase 0–1 scope

### Included now

- this PRD and architecture boundaries;
- source dataset and canonical schema contracts;
- target/label definitions to prevent later leakage;
- raw ingestion, cleaning, rejection accounting, and EDA;
- quality gates and automated tests.

### Explicitly deferred

- PostgreSQL/Alembic persistence (Phase 2);
- feature pipeline and RFM calculations (Phase 3);
- model training and scoring (Phases 4–8);
- FastAPI, React, RAG, and deployment (later phases).

## 7. ML target definitions fixed before modeling

### Churn

At snapshot date `T`, use only activity at or before `T`. A customer is labeled `churn = 1` when they make **no valid purchase** during `(T, T + 90 days]`; otherwise `0`.

Eligibility rules:

- known customer ID;
- at least one valid purchase before or at `T`;
- the dataset extends at least 90 days beyond `T`;
- cancellations/returns do not count as purchases.

### 30-day purchase propensity

At snapshot date `T`, label `purchase_next_30d = 1` if a customer makes at least one valid purchase during `(T, T + 30 days]`; otherwise `0`.

Eligibility rules mirror churn, with a 30-day observation horizon.

### Evaluation policy

- use chronological train/validation/test partitions;
- fit all preprocessing only on the training partition;
- tune decision thresholds on validation, not test;
- report ROC-AUC, PR-AUC, F1, precision, recall, confusion matrix, and calibration;
- compare against transparent recency and majority-class baselines;
- report slices by country and customer-value band where sample sizes permit.

## 8. Success metrics

### Data foundation

- 100% row reconciliation across purchase/return/rejected outputs;
- no invalid purchase row reaches the canonical purchase table;
- deterministic output for the same input and configuration;
- dataset ranges and key null rates appear in a machine-readable report.

### Model gates (future)

- each model beats its declared baseline on the untouched temporal test period;
- probability models include calibration evidence;
- recommendations report Recall@K, Precision@K, NDCG@K, and coverage;
- business-action metrics are kept distinct from offline model metrics.

### Product gates (future)

- users can trace each recommendation to source facts;
- every action suggestion records policy/model version;
- the UI never presents a score without an as-of date.

## 9. Non-functional requirements

- **Auditability:** outputs retain source row IDs, timestamps, and rejection reasons.
- **Isolation:** every future business record is scoped to a workspace.
- **Privacy:** customer identifiers remain pseudonymous in demos; no unnecessary PII enters prompts.
- **Reproducibility:** fixed package versions, seeded model routines, versioned features/models.
- **Reliability:** schema checks fail early and APIs later expose health/readiness endpoints.
- **Performance:** interactive customer/dashboard reads target p95 below 500 ms after data is prepared; batch computations remain offline.

## 10. Assumptions and risks

| Risk | Decision / mitigation |
| --- | --- |
| Retail data contains no explicit churn event | Use a documented inactivity target and test alternative horizons later. |
| `CustomerID` is missing on some lines | Preserve those rows in rejection output; do not invent customer identity. |
| Returns/cancellations distort revenue | Separate returns from purchases and publish gross, returned, and net amounts explicitly. |
| One UK-heavy retailer limits generalization | Treat results as a product demonstration, disclose dataset limits, and avoid universal claims. |
| Synthetic CRM enrichments may be added later | Clearly tag them as simulated and never mix them into claims about source data. |
| LLM can hallucinate calculations | Route metrics to deterministic analytics tools; LLM only explains supplied facts. |

## 11. Definition of done for Phase 0–1

- a new developer can install and run the sample pipeline from the README;
- source aliases normalize both Online Retail II and common Online Retail column names;
- all outputs reconcile to input rows;
- tests cover cancellations, missing identity, invalid quantity/price, duplicates, and bad dates;
- EDA artifacts are generated automatically from clean outputs;
- no model-performance or business-impact claim is made before evidence exists.
