# Architecture Decision Records

## ADR-001: UCI Online Retail II as the transaction core

**Status:** accepted

Use the two-year Online Retail II dataset because it supports repeated customer snapshots, seasonality, purchases, products, geography, and cancellations from one coherent source. Do not redistribute the full workbook in Git.

## ADR-002: Preserve returns separately

**Status:** accepted

Valid cancellation lines are not silently deleted. They are written to a returns table with negative quantities/amounts. Purchase behavior excludes them, while future net-revenue analytics can include both.

## ADR-003: Reject missing customer identity for customer intelligence

**Status:** accepted

Lines with no customer ID cannot safely feed customer segmentation, churn, propensity, or personalization. They remain auditable in the rejected output. A future financial aggregate pipeline may use them separately.

## ADR-004: Temporal targets and splits

**Status:** accepted

All predictive labels are defined from future observation windows relative to snapshot time, and evaluation is chronological. Random row splitting is prohibited because repeated customers and future information would leak.

## ADR-005: Modular monolith before services

**Status:** accepted

FastAPI will host the first production API as cohesive modules. Training remains an offline process. Service extraction requires measured operational justification.

## ADR-006: Structured analytics plus RAG

**Status:** accepted

Transaction metrics are computed by tested functions/queries. RAG is for unstructured approved knowledge and explanation context, not arithmetic over embedded transaction rows.

## ADR-007: Human-controlled actions

**Status:** accepted

The MVP recommends and records actions but does not autonomously email, discount, or contact customers.

## ADR-008: Exact numeric money in PostgreSQL

**Status:** accepted

Persist prices and line amounts as fixed-precision `NUMERIC`, not binary floating point. The loader recomputes line amount from validated quantity and unit price, and the database enforces the relationship.

## ADR-009: Content-fingerprint import idempotency

**Status:** accepted

Each workspace accepts a successful pair of processed purchase/return files once per versioned SHA-256 fingerprint. This prevents accidental duplicate full-snapshot loading without assuming that two legitimate invoice lines can be deduplicated from business fields alone.

## ADR-010: Explicit cutoff for every customer feature snapshot

**Status:** accepted

No customer feature is calculated without an `as_of` timestamp. Source queries and window calculations enforce the cutoff before aggregation, which enables leakage-safe historical training examples.

## ADR-011: Deterministic percentile RFM scoring

**Status:** accepted

Use midpoint percentile ranks for cohort-relative scores from 1–5. This handles tied values and small cohorts deterministically, unlike fragile quantile-bin edges. RFM scores remain separate from the Phase 4 clustering model.
