# GrowthPilot AI

Sales and customer-intelligence copilot for small and medium retail businesses.

This repository currently implements **Phase 0–1** of the build:

- product requirements and architecture decisions;
- leakage-safe churn and purchase-propensity definitions;
- a versioned transaction data contract;
- reproducible download of UCI Online Retail II;
- multi-sheet Excel/CSV ingestion;
- deterministic cleaning with row-level rejection reasons;
- dataset quality gates and reconciliation metrics;
- automated exploratory data analysis (EDA);
- unit and end-to-end tests.

The ML, API, UI, recommendations, and copilot layers intentionally come later. The foundation first establishes which records and facts every future model may trust.

## Product outcome

GrowthPilot converts raw retail activity into a daily decision queue:

```text
transactions -> customer state -> prediction -> next best action -> explanation -> outcome
```

Its future user-facing questions include:

- Which valuable customers are at risk of churn?
- Who is most likely to buy in the next 30 days?
- Which products should we recommend to a particular customer?
- Which customers should the sales team contact today, and why?

## Quick start

Requires Python 3.11+.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# Run the complete Phase 1 pipeline on the included safe fixture
growthpilot phase1 --input data/sample/online_retail_sample.csv

# Run tests
pytest
```

Generated files are written under `data/processed/` and `reports/eda/`.

## Run with the complete UCI dataset

The raw workbook is deliberately ignored by Git.

```bash
growthpilot download
growthpilot phase1 --input data/raw/online_retail_II.xlsx
```

If the UCI-hosted filename changes, pass an explicit official download URL:

```bash
growthpilot download --url "https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip"
```

The downloader accepts the official `.zip` archive or a direct `.xlsx` URL, verifies that the payload is structurally valid, and never overwrites an existing workbook unless `--force` is supplied.

## Phase 1 outputs

| Output | Purpose |
| --- | --- |
| `data/processed/transactions_clean.csv` | Canonical valid purchase lines |
| `data/processed/transactions_returns.csv` | Valid cancellation/return lines |
| `data/processed/transactions_rejected.csv` | Excluded rows with explicit reasons |
| `data/processed/data_quality_report.json` | Counts, reconciliation, ranges, and quality-gate results |
| `reports/eda/summary.json` | Core commercial and customer metrics |
| `reports/eda/monthly_revenue.csv` | Monthly sales trend |
| `reports/eda/country_summary.csv` | Country-level sales and customer summary |
| `reports/eda/top_products.csv` | Top products by net purchase revenue |
| `reports/eda/eda_overview.png` | Four-panel visual overview |
| `reports/eda/EDA_REPORT.md` | Human-readable Phase 1 report |

## Repository map

```text
growthpilot-ai/
├── docs/                   # Phase 0 product and technical decisions
├── src/growthpilot/data/   # Phase 1 ingestion, cleaning, QA, EDA
├── data/sample/            # Synthetic edge-case fixture only
├── tests/                  # Unit and end-to-end verification
├── reports/                # Generated EDA (ignored except placeholders)
└── pyproject.toml
```

See [docs/PHASE_0_PRD.md](docs/PHASE_0_PRD.md), [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), [docs/DATA_CONTRACT.md](docs/DATA_CONTRACT.md), and [docs/PHASE_1_RESULTS.md](docs/PHASE_1_RESULTS.md) before extending the project.

## Reproducibility and scope

- Dataset: UCI Online Retail II, a transactional retail dataset covering 2009-12-01 through 2011-12-09.
- Currency: the source records use sterling (£); all monetary features retain source currency and are not FX-normalized.
- The included sample is synthetic and exists only to test edge cases. It must never be presented as model evidence.
- Phase 1 does not train any model or claim an ML score.

## License note

Source code in this repository may be licensed separately by the repository owner. The UCI dataset is not redistributed here; follow the dataset page's citation and license requirements when downloading it.
