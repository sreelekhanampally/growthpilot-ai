import hashlib
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import TypeVar

import pandas as pd
from sqlalchemy import Engine, Select, func, insert, select, update
from sqlalchemy.orm import Session

from growthpilot.db.models import Customer, DataImport, Order, OrderItem, Product, Workspace
from growthpilot.db.session import session_scope

REQUIRED_LOAD_COLUMNS = {
    "source_row_id",
    "source_file",
    "source_sheet",
    "source_row_number",
    "invoice_no",
    "stock_code",
    "description",
    "quantity",
    "invoice_date",
    "unit_price",
    "customer_id",
    "country",
    "is_cancellation",
    "line_amount",
}

ModelT = TypeVar("ModelT")


class LoadValidationError(ValueError):
    """Raised when a processed file violates the Phase 1 output contract."""


@dataclass(frozen=True)
class ImportSummary:
    import_id: uuid.UUID
    workspace_id: uuid.UUID
    purchase_rows: int
    return_rows: int
    loaded_rows: int
    status: str
    skipped: bool = False


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _fingerprint(purchases_hash: str, returns_hash: str) -> str:
    value = f"growthpilot-db-contract-v1:{purchases_hash}:{returns_hash}"
    return hashlib.sha256(value.encode()).hexdigest()


def _batches(values: list[str] | list[tuple[str, str]], size: int = 500):
    for start in range(0, len(values), size):
        yield values[start : start + size]


def _read_chunks(path: Path, chunk_size: int):
    for chunk in pd.read_csv(path, chunksize=chunk_size, dtype=object):
        missing = sorted(REQUIRED_LOAD_COLUMNS - set(chunk.columns))
        if missing:
            raise LoadValidationError(f"{path.name} is missing: {', '.join(missing)}")
        yield chunk


def _text(value: object, field: str) -> str:
    if pd.isna(value) or not str(value).strip():
        raise LoadValidationError(f"{field} cannot be empty")
    return str(value).strip()


def _decimal(value: object, field: str) -> Decimal:
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise LoadValidationError(f"{field} must be numeric: {value}") from exc
    if not number.is_finite():
        raise LoadValidationError(f"{field} must be finite")
    return number


def _bool(value: object) -> bool:
    normalized = str(value).strip().lower()
    if normalized not in {"true", "false"}:
        raise LoadValidationError(f"is_cancellation must be true/false: {value}")
    return normalized == "true"


def _prepare_rows(chunk: pd.DataFrame, order_type: str) -> list[dict]:
    expected_cancellation = order_type == "return"
    rows: list[dict] = []
    for record in chunk.to_dict(orient="records"):
        quantity_decimal = _decimal(record["quantity"], "quantity")
        if quantity_decimal != quantity_decimal.to_integral_value():
            raise LoadValidationError("quantity must be an integer")
        quantity = int(quantity_decimal)
        unit_price = _decimal(record["unit_price"], "unit_price")
        line_amount = _decimal(record["line_amount"], "line_amount")
        invoice_date = pd.to_datetime(record["invoice_date"], errors="coerce")
        cancellation = _bool(record["is_cancellation"])
        if pd.isna(invoice_date):
            raise LoadValidationError("invoice_date must be valid")
        if cancellation != expected_cancellation:
            raise LoadValidationError(f"{order_type} file contains a mismatched cancellation row")
        if (order_type == "purchase" and quantity <= 0) or (
            order_type == "return" and quantity >= 0
        ):
            raise LoadValidationError(f"invalid quantity sign for {order_type}: {quantity}")
        calculated_line_amount = quantity * unit_price
        if unit_price < 0 or abs(line_amount - calculated_line_amount) > Decimal("0.0001"):
            raise LoadValidationError("price/line_amount invariant failed")
        rows.append(
            {
                "source_row_id": _text(record["source_row_id"], "source_row_id"),
                "source_file": _text(record["source_file"], "source_file"),
                "source_sheet": _text(record["source_sheet"], "source_sheet"),
                "source_row_number": int(
                    _decimal(record["source_row_number"], "source_row_number")
                ),
                "invoice_no": _text(record["invoice_no"], "invoice_no"),
                "stock_code": _text(record["stock_code"], "stock_code"),
                "description": None
                if pd.isna(record["description"])
                else str(record["description"]).strip(),
                "quantity": quantity,
                "invoice_date": pd.Timestamp(invoice_date).to_pydatetime(),
                "unit_price": unit_price,
                "customer_id": _text(record["customer_id"], "customer_id"),
                "country": _text(record["country"], "country"),
                "line_amount": calculated_line_amount,
                "order_type": order_type,
            }
        )
    return rows


def _workspace(session: Session, slug: str, name: str, currency: str) -> Workspace:
    workspace = session.scalar(select(Workspace).where(Workspace.slug == slug))
    if workspace:
        return workspace
    workspace = Workspace(slug=slug, name=name, currency=currency)
    session.add(workspace)
    session.flush()
    return workspace


def _lookup_pairs(session: Session, statement: Select, values: list[str]) -> dict[str, int]:
    result: dict[str, int] = {}
    for batch in _batches(sorted(set(values))):
        for key, row_id in session.execute(
            statement.where(statement.selected_columns[0].in_(batch))
        ):
            result[str(key)] = int(row_id)
    return result


def _ensure_customers(
    session: Session, workspace_id: uuid.UUID, rows: list[dict], cache: dict[str, int]
) -> None:
    customer_ids = sorted({row["customer_id"] for row in rows if row["customer_id"] not in cache})
    if not customer_ids:
        return
    statement = select(Customer.external_customer_id, Customer.id).where(
        Customer.workspace_id == workspace_id
    )
    cache.update(_lookup_pairs(session, statement, customer_ids))
    missing = [value for value in customer_ids if value not in cache]
    if missing:
        aggregates: dict[str, dict] = {}
        for row in rows:
            customer_id = row["customer_id"]
            if customer_id not in missing:
                continue
            current = aggregates.setdefault(
                customer_id,
                {
                    "workspace_id": workspace_id,
                    "external_customer_id": customer_id,
                    "country": row["country"],
                    "first_seen_at": row["invoice_date"],
                    "last_seen_at": row["invoice_date"],
                    "first_purchase_at": (
                        row["invoice_date"] if row["order_type"] == "purchase" else None
                    ),
                    "last_purchase_at": (
                        row["invoice_date"] if row["order_type"] == "purchase" else None
                    ),
                },
            )
            current["first_seen_at"] = min(current["first_seen_at"], row["invoice_date"])
            current["last_seen_at"] = max(current["last_seen_at"], row["invoice_date"])
            if row["order_type"] == "purchase":
                current["first_purchase_at"] = min(
                    current["first_purchase_at"] or row["invoice_date"], row["invoice_date"]
                )
                current["last_purchase_at"] = max(
                    current["last_purchase_at"] or row["invoice_date"], row["invoice_date"]
                )
        session.execute(insert(Customer), list(aggregates.values()))
        session.flush()
        cache.update(_lookup_pairs(session, statement, missing))


def _ensure_products(
    session: Session, workspace_id: uuid.UUID, rows: list[dict], cache: dict[str, int]
) -> None:
    stock_codes = sorted({row["stock_code"] for row in rows if row["stock_code"] not in cache})
    if not stock_codes:
        return
    statement = select(Product.stock_code, Product.id).where(Product.workspace_id == workspace_id)
    cache.update(_lookup_pairs(session, statement, stock_codes))
    missing = [value for value in stock_codes if value not in cache]
    if missing:
        descriptions: dict[str, str | None] = {value: None for value in missing}
        for row in rows:
            if row["stock_code"] in descriptions and row["description"]:
                descriptions[row["stock_code"]] = row["description"]
        session.execute(
            insert(Product),
            [
                {"workspace_id": workspace_id, "stock_code": code, "description": description}
                for code, description in descriptions.items()
            ],
        )
        session.flush()
        cache.update(_lookup_pairs(session, statement, missing))


def _ensure_orders(
    session: Session,
    workspace_id: uuid.UUID,
    rows: list[dict],
    customer_cache: dict[str, int],
    cache: dict[tuple[str, str], int],
) -> None:
    keys = sorted(
        {
            (row["invoice_no"], row["order_type"])
            for row in rows
            if (row["invoice_no"], row["order_type"]) not in cache
        }
    )
    if not keys:
        return
    for batch in _batches(keys, 200):
        invoices = [key[0] for key in batch]
        types = [key[1] for key in batch]
        statement = select(Order.invoice_no, Order.order_type, Order.id).where(
            Order.workspace_id == workspace_id,
            Order.invoice_no.in_(invoices),
            Order.order_type.in_(types),
        )
        for invoice_no, order_type, row_id in session.execute(statement):
            cache[(invoice_no, order_type)] = int(row_id)
    missing = [key for key in keys if key not in cache]
    if missing:
        examples: dict[tuple[str, str], dict] = {}
        missing_set = set(missing)
        for row in rows:
            key = (row["invoice_no"], row["order_type"])
            if key in missing_set and key not in examples:
                examples[key] = {
                    "workspace_id": workspace_id,
                    "customer_id": customer_cache[row["customer_id"]],
                    "invoice_no": row["invoice_no"],
                    "order_type": row["order_type"],
                    "invoice_date": row["invoice_date"],
                    "country": row["country"],
                }
        session.execute(insert(Order), list(examples.values()))
        session.flush()
        for batch in _batches(missing, 200):
            invoices = [key[0] for key in batch]
            types = [key[1] for key in batch]
            statement = select(Order.invoice_no, Order.order_type, Order.id).where(
                Order.workspace_id == workspace_id,
                Order.invoice_no.in_(invoices),
                Order.order_type.in_(types),
            )
            for invoice_no, order_type, row_id in session.execute(statement):
                cache[(invoice_no, order_type)] = int(row_id)


def _load_file(
    session: Session,
    path: Path,
    order_type: str,
    workspace_id: uuid.UUID,
    import_id: uuid.UUID,
    chunk_size: int,
    customer_cache: dict[str, int],
    product_cache: dict[str, int],
    order_cache: dict[tuple[str, str], int],
) -> int:
    loaded = 0
    for chunk in _read_chunks(path, chunk_size):
        rows = _prepare_rows(chunk, order_type)
        _ensure_customers(session, workspace_id, rows, customer_cache)
        _ensure_products(session, workspace_id, rows, product_cache)
        _ensure_orders(session, workspace_id, rows, customer_cache, order_cache)
        mappings = [
            {
                "workspace_id": workspace_id,
                "order_id": order_cache[(row["invoice_no"], order_type)],
                "product_id": product_cache[row["stock_code"]],
                "data_import_id": import_id,
                "quantity": row["quantity"],
                "unit_price": row["unit_price"],
                "line_amount": row["line_amount"],
                "source_row_id": row["source_row_id"],
                "source_file": row["source_file"],
                "source_sheet": row["source_sheet"],
                "source_row_number": row["source_row_number"],
            }
            for row in rows
        ]
        session.execute(insert(OrderItem), mappings)
        loaded += len(mappings)
    return loaded


def _refresh_customer_dates(session: Session, workspace_id: uuid.UUID) -> None:
    first_seen = (
        select(func.min(Order.invoice_date))
        .where(Order.customer_id == Customer.id)
        .correlate(Customer)
        .scalar_subquery()
    )
    last_seen = (
        select(func.max(Order.invoice_date))
        .where(Order.customer_id == Customer.id)
        .correlate(Customer)
        .scalar_subquery()
    )
    first_purchase = (
        select(func.min(Order.invoice_date))
        .where(Order.customer_id == Customer.id, Order.order_type == "purchase")
        .correlate(Customer)
        .scalar_subquery()
    )
    last_purchase = (
        select(func.max(Order.invoice_date))
        .where(Order.customer_id == Customer.id, Order.order_type == "purchase")
        .correlate(Customer)
        .scalar_subquery()
    )
    session.execute(
        update(Customer)
        .where(Customer.workspace_id == workspace_id)
        .values(
            first_seen_at=first_seen,
            last_seen_at=last_seen,
            first_purchase_at=first_purchase,
            last_purchase_at=last_purchase,
        )
    )


def load_processed_data(
    engine: Engine,
    purchases_path: Path,
    returns_path: Path,
    *,
    workspace_slug: str = "demo-retail",
    workspace_name: str = "Demo Retail",
    currency: str = "GBP",
    chunk_size: int = 25_000,
) -> ImportSummary:
    purchases_path, returns_path = Path(purchases_path), Path(returns_path)
    for path in (purchases_path, returns_path):
        if not path.exists():
            raise FileNotFoundError(path)
    if chunk_size < 1:
        raise ValueError("chunk_size must be positive")

    purchases_hash = _sha256(purchases_path)
    returns_hash = _sha256(returns_path)
    fingerprint = _fingerprint(purchases_hash, returns_hash)

    with session_scope(engine) as session:
        workspace = _workspace(session, workspace_slug, workspace_name, currency.upper())
        previous = session.scalar(
            select(DataImport).where(
                DataImport.workspace_id == workspace.id,
                DataImport.dataset_fingerprint == fingerprint,
                DataImport.status == "succeeded",
            )
        )
        if previous:
            return ImportSummary(
                previous.id,
                workspace.id,
                previous.purchase_rows,
                previous.return_rows,
                previous.loaded_rows,
                previous.status,
                skipped=True,
            )

        data_import = DataImport(
            workspace_id=workspace.id,
            source_name=f"{purchases_path.name} + {returns_path.name}",
            purchases_sha256=purchases_hash,
            returns_sha256=returns_hash,
            dataset_fingerprint=fingerprint,
            status="running",
        )
        session.add(data_import)
        session.flush()

        customer_cache: dict[str, int] = {}
        product_cache: dict[str, int] = {}
        order_cache: dict[tuple[str, str], int] = {}
        purchase_rows = _load_file(
            session,
            purchases_path,
            "purchase",
            workspace.id,
            data_import.id,
            chunk_size,
            customer_cache,
            product_cache,
            order_cache,
        )
        return_rows = _load_file(
            session,
            returns_path,
            "return",
            workspace.id,
            data_import.id,
            chunk_size,
            customer_cache,
            product_cache,
            order_cache,
        )
        _refresh_customer_dates(session, workspace.id)
        loaded_rows = session.scalar(
            select(func.count(OrderItem.id)).where(OrderItem.data_import_id == data_import.id)
        )
        expected = purchase_rows + return_rows
        if loaded_rows != expected:
            raise RuntimeError(f"Database reconciliation failed: {loaded_rows} != {expected}")

        data_import.purchase_rows = purchase_rows
        data_import.return_rows = return_rows
        data_import.loaded_rows = int(loaded_rows or 0)
        data_import.status = "succeeded"
        data_import.completed_at = datetime.now(UTC)
        session.flush()

        return ImportSummary(
            data_import.id,
            workspace.id,
            purchase_rows,
            return_rows,
            data_import.loaded_rows,
            data_import.status,
        )
