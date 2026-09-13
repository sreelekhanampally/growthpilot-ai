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
