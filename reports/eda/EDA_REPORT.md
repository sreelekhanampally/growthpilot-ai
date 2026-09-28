# Phase 1 EDA Report

## Executive summary

| Metric | Value |
| --- | ---: |
| Gross purchase revenue | £865,258.09 |
| Returned value | £1,563.48 |
| Net revenue | £863,694.61 |
| Purchase orders | 3,464 |
| Identified customers | 240 |
| Products | 80 |
| Countries | 6 |
| Average order value | £249.79 |

## Data quality

- Input rows: 13,981
- Accepted purchase rows: 13,858
- Accepted return rows: 123
- Rejected rows: 0
- Acceptance rate: 100.00%
- All required quality gates passed: **True**

## Initial observations

- Highest-revenue country in the cleaned purchase data: **United Kingdom**.
- Highest-revenue product in the cleaned purchase data: **Demo product GP0031**.
- Revenue values are in the source currency (sterling) and are not FX-normalized.
- These are descriptive observations, not causal findings or model results.

## Generated companion files

- `monthly_revenue.csv`
- `country_summary.csv`
- `top_products.csv`
- `summary.json`
- `eda_overview.png`
