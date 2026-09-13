# Phase 1 Verification Results

Run date: 2026-09-13  
Dataset: UCI Online Retail II  
Coverage: 2009-12-01 07:45 through 2011-12-09 12:50

## Classification and quality

| Metric | Result |
| --- | ---: |
| Input rows | 1,067,371 |
| Valid purchase rows | 779,495 |
| Valid return rows | 18,390 |
| Rejected rows | 269,486 |
| Acceptance rate | 74.75% |
| Customers across accepted rows | 5,942 |
| Products across accepted rows | 4,646 |
| Required quality gates | 7/7 passed |

Rows can contain more than one rejection reason, so reason counts do not sum to rejected rows.

| Rejection reason | Count |
| --- | ---: |
| Missing customer ID | 243,007 |
| Exact duplicate after canonicalization | 34,335 |
| Non-cancellation with nonpositive quantity | 3,457 |
| Negative unit price | 5 |
| Cancellation with positive quantity | 1 |

## Descriptive commercial metrics

These figures are descriptive pipeline outputs, not model results or causal business-impact claims.

| Metric | Result |
| --- | ---: |
| Gross purchase revenue | £17,374,804.27 |
| Returned value | £1,084,812.98 |
| Net revenue | £16,289,991.29 |
| Valid purchase orders | 36,975 |
| Purchasing customers | 5,881 |
| Purchased products | 4,631 |
| Countries | 41 |
| Average purchase-order value | £469.91 |

## Verification performed

- end-to-end run over both workbook sheets;
- row reconciliation and unique source-row checks;
- accepted quantity, price, customer, and date invariants;
- six automated tests covering schema aliases and edge cases;
- Ruff static checks;
- automated CSV, JSON, Markdown, and PNG EDA generation.

The full workbook and large row-level outputs are intentionally excluded from the deliverable archive and Git. Run `growthpilot download` followed by the Phase 1 command in the README to reproduce them.
