from decimal import Decimal
from pathlib import Path

from sqlalchemy import func, select

from growthpilot.data.pipeline import run_phase1
from growthpilot.db.loader import load_processed_data
from growthpilot.db.migrate import upgrade_database
from growthpilot.db.models import Customer, CustomerFeatureSnapshot, FeatureRun
from growthpilot.db.session import build_engine, session_scope
from growthpilot.features.contract import DEFAULT_FEATURE_VERSION
from growthpilot.features.service import build_and_store_features

SAMPLE = Path(__file__).parents[1] / "data" / "sample" / "online_retail_sample.csv"


def _database(tmp_path: Path):
    processed = tmp_path / "processed"
    run_phase1(SAMPLE, processed_dir=processed, report_dir=tmp_path / "reports")
    engine = build_engine(f"sqlite+pysqlite:///{tmp_path / 'features.sqlite'}")
    upgrade_database(str(engine.url))
    load_processed_data(
        engine,
        processed / "transactions_clean.csv",
        processed / "transactions_returns.csv",
        chunk_size=2,
    )
    return engine


def test_cutoff_excludes_future_purchases_and_rfm_is_valid(tmp_path: Path) -> None:
    engine = _database(tmp_path)
    output = tmp_path / "customer_features.csv"
    summary = build_and_store_features(
        engine,
        workspace_slug="demo-retail",
        as_of="2010-02-01T00:00:00",
        feature_version=DEFAULT_FEATURE_VERSION,
        output_path=output,
    )

    assert summary.customer_count == 3
    assert output.exists()
    with session_scope(engine) as session:
        customer_id = session.scalar(
            select(Customer.id).where(Customer.external_customer_id == "13085")
        )
        snapshot = session.scalar(
            select(CustomerFeatureSnapshot).where(
                CustomerFeatureSnapshot.customer_id == customer_id,
                CustomerFeatureSnapshot.as_of == summary.as_of,
            )
        )
        assert snapshot.frequency_orders == 1
        assert snapshot.monetary_value == Decimal("164.4000")
        assert snapshot.total_items == 24
        assert snapshot.unique_products == 2
        assert snapshot.last_purchase_at < summary.as_of
        assert 1 <= snapshot.rfm_recency_score <= 5
        assert 1 <= snapshot.rfm_frequency_score <= 5
        assert 1 <= snapshot.rfm_monetary_score <= 5
        assert snapshot.rfm_code == (
            f"{snapshot.rfm_recency_score}"
            f"{snapshot.rfm_frequency_score}"
            f"{snapshot.rfm_monetary_score}"
        )


def test_feature_build_is_idempotent_and_historical_snapshot_is_stable(tmp_path: Path) -> None:
    engine = _database(tmp_path)
    early = build_and_store_features(
        engine,
        workspace_slug="demo-retail",
        as_of="2010-02-01T00:00:00",
        feature_version=DEFAULT_FEATURE_VERSION,
    )
    duplicate = build_and_store_features(
        engine,
        workspace_slug="demo-retail",
        as_of="2010-02-01T00:00:00",
        feature_version=DEFAULT_FEATURE_VERSION,
    )
    late = build_and_store_features(
        engine,
        workspace_slug="demo-retail",
        as_of="2010-06-02T00:00:00",
        feature_version=DEFAULT_FEATURE_VERSION,
    )

    assert duplicate.skipped is True
    assert duplicate.feature_run_id == early.feature_run_id
    assert late.feature_run_id != early.feature_run_id

    with session_scope(engine) as session:
        customer_id = session.scalar(
            select(Customer.id).where(Customer.external_customer_id == "13085")
        )
        early_snapshot = session.scalar(
            select(CustomerFeatureSnapshot).where(
                CustomerFeatureSnapshot.customer_id == customer_id,
                CustomerFeatureSnapshot.as_of == early.as_of,
            )
        )
        late_snapshot = session.scalar(
            select(CustomerFeatureSnapshot).where(
                CustomerFeatureSnapshot.customer_id == customer_id,
                CustomerFeatureSnapshot.as_of == late.as_of,
            )
        )
        assert early_snapshot.frequency_orders == 1
        assert late_snapshot.frequency_orders == 2
        assert early_snapshot.monetary_value == Decimal("164.4000")
        assert late_snapshot.monetary_value == Decimal("189.9000")
        assert session.scalar(select(func.count(FeatureRun.id))) == 2
        assert session.scalar(select(func.count(CustomerFeatureSnapshot.id))) == 6


def test_window_features_are_monotonic(tmp_path: Path) -> None:
    engine = _database(tmp_path)
    summary = build_and_store_features(
        engine,
        workspace_slug="demo-retail",
        as_of="2010-06-02T00:00:00",
        feature_version=DEFAULT_FEATURE_VERSION,
    )

    with session_scope(engine) as session:
        snapshots = session.scalars(
            select(CustomerFeatureSnapshot).where(
                CustomerFeatureSnapshot.feature_run_id == summary.feature_run_id
            )
        ).all()
        assert snapshots
        for snapshot in snapshots:
            assert snapshot.orders_30d <= snapshot.orders_90d
            assert snapshot.orders_90d <= snapshot.orders_180d
            assert snapshot.orders_180d <= snapshot.frequency_orders
            assert snapshot.revenue_30d <= snapshot.revenue_90d
            assert snapshot.revenue_90d <= snapshot.revenue_180d
            assert snapshot.revenue_180d <= snapshot.monetary_value
