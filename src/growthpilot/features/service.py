import hashlib
import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import pandas as pd
from sqlalchemy import Engine, delete, func, insert, select
from sqlalchemy.orm import Session

from growthpilot.db.models import (
    Customer,
    CustomerFeatureSnapshot,
    DataImport,
    FeatureRun,
    Order,
    OrderItem,
    Workspace,
)
from growthpilot.db.session import session_scope
from growthpilot.features.builder import build_customer_features
from growthpilot.features.contract import FEATURE_CONTRACT_VERSION, parse_as_of


@dataclass(frozen=True)
class FeatureBuildSummary:
    feature_run_id: uuid.UUID
    workspace_id: uuid.UUID
    as_of: datetime
    feature_version: str
    source_fingerprint: str
    customer_count: int
    output_path: Path | None
    skipped: bool = False


def _workspace(session: Session, slug: str) -> Workspace:
    workspace = session.scalar(select(Workspace).where(Workspace.slug == slug))
    if not workspace:
        raise ValueError(f"Workspace does not exist: {slug}")
    return workspace


def _source_fingerprint(
    session: Session, workspace_id: uuid.UUID, as_of: datetime, feature_version: str
) -> str:
    fingerprints = session.scalars(
        select(DataImport.dataset_fingerprint)
        .distinct()
        .join(OrderItem, OrderItem.data_import_id == DataImport.id)
        .join(Order, Order.id == OrderItem.order_id)
        .where(Order.workspace_id == workspace_id, Order.invoice_date <= as_of)
    ).all()
    if not fingerprints:
        raise ValueError("No imported transaction data exists at this cutoff")
    content = ":".join(
        [FEATURE_CONTRACT_VERSION, feature_version, as_of.isoformat(), *sorted(fingerprints)]
    )
    return hashlib.sha256(content.encode()).hexdigest()


def _read_transactions(session: Session, workspace_id: uuid.UUID, as_of: datetime) -> pd.DataFrame:
    statement = (
        select(
            Customer.id.label("customer_id"),
            Customer.external_customer_id,
            Order.invoice_no,
            Order.order_type,
            Order.invoice_date,
            OrderItem.product_id,
            OrderItem.quantity,
            OrderItem.line_amount,
        )
        .select_from(OrderItem)
        .join(Order, Order.id == OrderItem.order_id)
        .join(Customer, Customer.id == Order.customer_id)
        .where(Order.workspace_id == workspace_id, Order.invoice_date <= as_of)
    )
    return pd.read_sql(statement, session.connection())


def _decimal(value: object, places: int) -> Decimal | None:
    if pd.isna(value):
        return None
    quantum = Decimal(1).scaleb(-places)
    return Decimal(str(value)).quantize(quantum, rounding=ROUND_HALF_UP)


def _snapshot_mappings(
    frame: pd.DataFrame,
    *,
    run_id: uuid.UUID,
    workspace_id: uuid.UUID,
    as_of: datetime,
    feature_version: str,
) -> list[dict]:
    money = {
        "monetary_value",
        "net_revenue",
        "average_order_value",
        "average_basket_size",
        "purchase_interval_mean_days",
        "purchase_interval_std_days",
        "revenue_30d",
        "revenue_90d",
        "revenue_180d",
        "revenue_previous_30d",
        "returned_value",
    }
    ratios = {"revenue_growth_30d", "cancellation_rate", "return_value_rate"}
    excluded = {"external_customer_id"}
    mappings: list[dict] = []
    for record in frame.to_dict(orient="records"):
        mapping = {
            "feature_run_id": run_id,
            "workspace_id": workspace_id,
            "as_of": as_of,
            "feature_version": feature_version,
        }
        for key, value in record.items():
            if key in excluded or key in {"as_of", "feature_version"}:
                continue
            if key in money:
                mapping[key] = _decimal(value, 4)
            elif key in ratios:
                mapping[key] = _decimal(value, 6)
            elif key in {"first_purchase_at", "last_purchase_at"}:
                mapping[key] = pd.Timestamp(value).to_pydatetime()
            elif key == "rfm_code":
                mapping[key] = str(value)
            else:
                mapping[key] = int(value)
        mappings.append(mapping)
    return mappings


def build_and_store_features(
    engine: Engine,
    *,
    workspace_slug: str,
    as_of: str | datetime | pd.Timestamp,
    feature_version: str,
    output_path: Path | None = None,
) -> FeatureBuildSummary:
    cutoff = parse_as_of(as_of)
    if not feature_version.strip():
        raise ValueError("feature_version cannot be empty")

    generated: pd.DataFrame | None = None
    with session_scope(engine) as session:
        workspace = _workspace(session, workspace_slug)
        source_fingerprint = _source_fingerprint(session, workspace.id, cutoff, feature_version)
        existing = session.scalar(
            select(FeatureRun).where(
                FeatureRun.workspace_id == workspace.id,
                FeatureRun.as_of == cutoff,
                FeatureRun.feature_version == feature_version,
            )
        )
        if existing and existing.source_fingerprint == source_fingerprint:
            stored_count = session.scalar(
                select(func.count(CustomerFeatureSnapshot.id)).where(
                    CustomerFeatureSnapshot.feature_run_id == existing.id
                )
            )
            if stored_count == existing.customer_count:
                return FeatureBuildSummary(
                    existing.id,
                    workspace.id,
                    cutoff,
                    feature_version,
                    source_fingerprint,
                    existing.customer_count,
                    None,
                    skipped=True,
                )

        transactions = _read_transactions(session, workspace.id, cutoff)
        generated = build_customer_features(
            transactions, as_of=cutoff, feature_version=feature_version
        )
        if existing:
            session.execute(delete(FeatureRun).where(FeatureRun.id == existing.id))
            session.flush()

        feature_run = FeatureRun(
            workspace_id=workspace.id,
            as_of=cutoff,
            feature_version=feature_version,
            source_fingerprint=source_fingerprint,
            customer_count=len(generated),
        )
        session.add(feature_run)
        session.flush()
        mappings = _snapshot_mappings(
            generated,
            run_id=feature_run.id,
            workspace_id=workspace.id,
            as_of=cutoff,
            feature_version=feature_version,
        )
        session.execute(insert(CustomerFeatureSnapshot), mappings)
        stored_count = session.scalar(
            select(func.count(CustomerFeatureSnapshot.id)).where(
                CustomerFeatureSnapshot.feature_run_id == feature_run.id
            )
        )
        if stored_count != len(generated):
            raise RuntimeError(f"Feature reconciliation failed: {stored_count} != {len(generated)}")
        summary = FeatureBuildSummary(
            feature_run.id,
            workspace.id,
            cutoff,
            feature_version,
            source_fingerprint,
            len(generated),
            output_path,
        )

    if output_path is not None and generated is not None:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        generated.to_csv(output_path, index=False)
    return summary
