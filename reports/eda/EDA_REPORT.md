# Phase 1 EDA Report

## Executive summary

| Metric | Value |
| --- | ---: |
| Gross purchase revenue | £17,374,804.27 |
| Returned value | £1,084,812.98 |
| Net revenue | £16,289,991.29 |
| Purchase orders | 36,975 |
| Identified customers | 5,881 |
| Products | 4,631 |
| Countries | 41 |
| Average order value | £469.91 |

## Data quality

- Input rows: 1,067,371
- Accepted purchase rows: 779,495
- Accepted return rows: 18,390
- Rejected rows: 269,486
- Acceptance rate: 74.75%
- All required quality gates passed: **True**

## Initial observations

- Highest-revenue country in the cleaned purchase data: **United Kingdom**.
- Highest-revenue product in the cleaned purchase data: **REGENCY CAKESTAND 3 TIER**.
- Revenue values are in the source currency (sterling) and are not FX-normalized.
- These are descriptive observations, not causal findings or model results.

## Generated companion files

- `monthly_revenue.csv`
- `country_summary.csv`
- `top_products.csv`
- `summary.json`
- `eda_overview.png`
