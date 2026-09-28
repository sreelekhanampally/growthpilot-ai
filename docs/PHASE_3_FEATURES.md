# Phase 3 — Customer Feature Pipeline and RFM

## Outcome

Phase 3 produces versioned customer feature snapshots from normalized transaction data. Every snapshot is calculated only from transactions at or before an explicit `as_of` timestamp, making the output safe for future historical labels and temporal model evaluation.

## Leakage boundary

For snapshot time `T`:

- eligible customers have at least one valid purchase at or before `T`;
- lifetime features use purchase/return activity at or before `T`;
- a 30-day window means `(T − 30 days, T]`;
- the previous 30-day window means `(T − 60 days, T − 30 days]`;
- transactions after `T` are never read into the snapshot;
- return-only customers are retained in the relational store but are not eligible for an RFM row.

This permits later creation of many historical snapshots without using information from their future observation windows.

## Feature contract v1

### RFM and customer value

| Feature | Definition |
| --- | --- |
| `recency_days` | completed days between `T` and last valid purchase |
| `frequency_orders` | distinct valid purchase invoices through `T` |
| `monetary_value` | gross valid purchase revenue through `T` |
| `net_revenue` | gross purchase revenue minus observed returned value |
| `customer_tenure_days` | completed days between first purchase and `T` |

### Basket and product behavior

| Feature | Definition |
| --- | --- |
| `total_items` | purchased units through `T` |
| `unique_products` | distinct purchased product IDs through `T` |
| `average_order_value` | monetary value divided across purchase invoices |
| `average_basket_size` | mean purchased units per invoice |
| `purchase_interval_mean_days` | mean time between consecutive purchase invoices |
| `purchase_interval_std_days` | population standard deviation of purchase intervals |

Purchase-interval values are null when a customer has fewer than two purchase invoices.

### Recent behavior

The pipeline calculates purchase-order counts and purchase revenue for trailing 30, 90, and 180-day windows. It also stores the immediately previous 30-day count/revenue, absolute order-frequency change, and relative revenue growth. Revenue growth is null when the previous window has zero revenue, avoiding artificial infinity.

### Return behavior

| Feature | Definition |
| --- | --- |
| `return_orders` | distinct cancellation invoices through `T` |
| `returned_value` | absolute value of valid cancellation lines |
| `cancellation_rate` | return invoices divided by purchase plus return invoices |
| `return_value_rate` | returned value divided by gross purchase revenue |

## RFM scoring policy

RFM component scores range from 1 to 5 and are relative to all eligible customers in the same workspace and cutoff:

- lower recency receives a higher score;
- higher frequency receives a higher score;
- higher monetary value receives a higher score.

Scores use deterministic midpoint percentile ranks instead of `qcut`, which remains stable when many customers share the same value. `rfm_code` concatenates the three component scores and `rfm_total_score` ranges from 3 to 15.

These are behavioral scores, not the business-readable/K-Means segments introduced in Phase 4.

## Persistence and reproducibility

`feature_runs` records the workspace, cutoff, feature version, eligible-customer count, and SHA-256 source fingerprint. `customer_feature_snapshots` stores the feature vector with database checks and two uniqueness boundaries:

- one customer per feature run;
- one workspace/customer/cutoff/version snapshot.

The fingerprint combines the contract version, feature version, cutoff, and relevant successful data-import fingerprints. Repeating an unchanged build skips duplicate work.

## Commands

Apply the new migration first:

```bash
growthpilot db-upgrade
```

Build the final-dataset snapshot and CSV export:

```bash
growthpilot build-features --as-of 2011-12-09T12:50:00
```

Build a historical snapshot:

```bash
growthpilot build-features \
  --as-of 2010-06-30T23:59:59 \
  --feature-version customer-features-v1 \
  --output data/processed/customer_features_2010_06_30.csv
```

The explicit cutoff is intentionally required; silently using the current date would make results irreproducible and meaningless for this historical dataset.

## Scale safeguard

Phase 3 adds an index on `order_items.order_id`. Without it, the database can find the cutoff-valid orders but may repeatedly scan the entire item table while joining each order to its lines. The full-dataset validation caught this query-plan issue; the index turns that repeated scan into indexed lookups.

## Full-dataset verification

Cutoff: `2011-12-09T12:50:00`
Feature version: `customer-features-v1`

| Check | Result |
| --- | ---: |
| Accepted transaction lines read | 797,885 |
| Eligible customer snapshots | 5,881 |
| Feature columns | 36 |
| Distinct stored customers | 5,881 |
| Purchase orders reconciled | 36,975 |
| Gross monetary value reconciled | £17,374,804.27 |
| Customers with observed returns | 2,511 |
| Customers with one purchase | 1,626 |
| Null purchase-interval values | 1,626 |
| Full build time on the validation SQLite database | 8.3 seconds |
| Unchanged rerun/skip time | 1.1 seconds |

The equality between one-purchase customers and missing purchase-interval values is an additional semantic check: an interval cannot exist until a second order occurs.

Observed distribution checks:

- recency ranged from 0 to 738 completed days, with a median of 95;
- purchase frequency ranged from 1 to 398 orders, with a median of 3;
- RFM total scores covered the full 3–15 range with a median of 9;
- all order and revenue windows were monotonic;
- all generated customer IDs were unique;
- database snapshot count matched the generated frame exactly.

The runtime is an environment-specific engineering benchmark, not a production SLA. Production remains PostgreSQL; SQLite is used for portable full-scale verification.
