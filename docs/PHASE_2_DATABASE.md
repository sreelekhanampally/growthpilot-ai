# Phase 2 — PostgreSQL Foundation

## Outcome

Phase 2 converts the validated Phase 1 files into a normalized, workspace-isolated relational model. It supplies versioned Alembic migrations and an idempotent, chunked loader suitable for the complete Online Retail II output.

## Entity relationship model

```mermaid
erDiagram
    WORKSPACES ||--o{ DATA_IMPORTS : owns
    WORKSPACES ||--o{ CUSTOMERS : owns
    WORKSPACES ||--o{ PRODUCTS : owns
    CUSTOMERS ||--o{ ORDERS : places
    ORDERS ||--|{ ORDER_ITEMS : contains
    PRODUCTS ||--o{ ORDER_ITEMS : identifies
    DATA_IMPORTS ||--o{ ORDER_ITEMS : traces
```

## Tables

| Table | Role | Important invariant |
| --- | --- | --- |
| `workspaces` | tenant/business boundary | globally unique slug |
| `data_imports` | file hashes, status, reconciliation counts | one dataset fingerprint per workspace |
| `customers` | pseudonymous customer dimension | external ID unique inside workspace |
| `products` | product dimension | stock code unique inside workspace |
| `orders` | invoice header for purchase or return | invoice/type unique inside workspace |
| `order_items` | signed transactional fact | source row unique inside workspace |

All business rows carry or inherit a workspace boundary. System-generated UUIDs identify workspaces/imports; bigint identities support high-volume transactional entities.

## Exact money and return handling

- `unit_price` is `NUMERIC(14,4)`.
- `line_amount` is `NUMERIC(18,4)`.
- a database check enforces `line_amount = quantity × unit_price`, rounded to the stored four-decimal precision.
- purchase quantities are positive; cancellation/return quantities remain negative.
- returns remain separate order headers rather than being silently subtracted from original invoices.

## Loader behavior

1. SHA-256 hash both processed input files.
2. Build a versioned dataset fingerprint.
3. Skip an already-successful fingerprint inside the same workspace.
4. Read CSV data in bounded chunks (25,000 rows by default).
5. validate the Phase 1 contract again at the persistence boundary;
6. create/reuse customer, product, and order dimensions;
7. insert source-traceable items;
8. recompute customer first/last seen and purchase dates;
9. reconcile stored item count before marking the import successful.

The load is transactional. A validation or database failure rolls back that attempt rather than publishing a partial successful import.

## Commands

Set the connection URL:

```bash
export DATABASE_URL="postgresql+psycopg://growthpilot:growthpilot@localhost:5432/growthpilot"
```

PowerShell:

```powershell
$env:DATABASE_URL="postgresql+psycopg://growthpilot:growthpilot@localhost:5432/growthpilot"
```

Apply the schema and load the current Phase 1 files:

```bash
growthpilot db-upgrade
growthpilot load-db
```

Optional explicit inputs:

```bash
growthpilot load-db \
  --purchases data/processed/transactions_clean.csv \
  --returns data/processed/transactions_returns.csv \
  --workspace-slug demo-retail \
  --workspace-name "Demo Retail" \
  --currency GBP \
  --chunk-size 25000
```

Re-running the exact same files returns `Skipped existing import` and does not duplicate rows.

## Indexing decisions

- customer last-purchase date supports recency queries;
- workspace/order date supports revenue windows and snapshot generation;
- customer/order date supports Customer 360 timelines;
- product item index supports product/customer aggregation;
- import item index supports audit and reconciliation.

Indexes for later feature or model tables will be added with those tables, based on their actual access patterns.

## Verification

Automated tests apply the Alembic migration to a temporary relational database, load the Phase 1 edge-case fixture in two-row chunks, verify exact table counts and customer dates, reload it to confirm idempotency, and load it into a second workspace to verify tenant isolation.

Production targets PostgreSQL. SQLite is used only for fast, deterministic migration/loader tests and is not the deployment database.

### Full-dataset scale run

The complete accepted Phase 1 outputs were migrated and loaded successfully:

| Stored entity | Count |
| --- | ---: |
| Workspaces | 1 |
| Successful imports | 1 |
| Customers | 5,942 |
| Products | 4,646 |
| Purchase orders | 36,975 |
| Return orders | 7,901 |
| Order items | 797,885 |
| Return-only customers | 61 |

The stored item count exactly matched 779,495 purchase lines plus 18,390 return lines. Re-running the identical full dataset created no new records.
