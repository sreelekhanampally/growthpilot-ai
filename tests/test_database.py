from pathlib import Path

from alembic import command
from sqlalchemy import func, inspect, select

from growthpilot.config import find_project_root
from growthpilot.data.pipeline import run_phase1
from growthpilot.db.loader import load_processed_data
from growthpilot.db.migrate import alembic_config, upgrade_database
from growthpilot.db.models import Customer, DataImport, Order, OrderItem, Product, Workspace
from growthpilot.db.session import build_engine, resolve_database_url, session_scope

SAMPLE = Path(__file__).parents[1] / "data" / "sample" / "online_retail_sample.csv"


def test_project_root_discovery_finds_repository_from_nested_directory(tmp_path: Path) -> None:
    project_root = tmp_path / "checkout"
    nested = project_root / "frontend" / "src"
    nested.mkdir(parents=True)
    (project_root / "migrations").mkdir()
    (project_root / "alembic.ini").write_text("[alembic]\n", encoding="utf-8")

    assert find_project_root(nested) == project_root


def test_managed_postgres_url_uses_installed_psycopg3_driver() -> None:
    resolved = resolve_database_url("postgresql://user:password@example.test:5432/app")

    assert resolved.startswith("postgresql+psycopg://")


def _prepared_sample(tmp_path: Path) -> tuple[Path, Path]:
    processed = tmp_path / "processed"
    run_phase1(SAMPLE, processed_dir=processed, report_dir=tmp_path / "reports")
    return processed / "transactions_clean.csv", processed / "transactions_returns.csv"


def test_migration_creates_normalized_schema(tmp_path: Path) -> None:
    engine = build_engine(f"sqlite+pysqlite:///{tmp_path / 'schema.sqlite'}")
    upgrade_database(str(engine.url))

    assert {
        "alembic_version",
        "workspaces",
        "data_imports",
        "customers",
        "products",
        "orders",
        "order_items",
    }.issubset(inspect(engine).get_table_names())
    command.check(alembic_config(str(engine.url)))


def test_loader_reconciles_and_is_idempotent(tmp_path: Path) -> None:
    purchases, returns = _prepared_sample(tmp_path)
    engine = build_engine(f"sqlite+pysqlite:///{tmp_path / 'load.sqlite'}")
    upgrade_database(str(engine.url))

    first = load_processed_data(engine, purchases, returns, chunk_size=2)
    second = load_processed_data(engine, purchases, returns, chunk_size=2)

    assert first.loaded_rows == 9
    assert first.purchase_rows == 8
    assert first.return_rows == 1
    assert first.skipped is False
    assert second.skipped is True
    assert second.import_id == first.import_id

    with session_scope(engine) as session:
        assert session.scalar(select(func.count(Workspace.id))) == 1
        assert session.scalar(select(func.count(DataImport.id))) == 1
        assert session.scalar(select(func.count(Customer.id))) == 4
        assert session.scalar(select(func.count(Product.id))) == 9
        assert session.scalar(select(func.count(Order.id))) == 8
        assert session.scalar(select(func.count(OrderItem.id))) == 9

        repeat_customer = session.scalar(
            select(Customer).where(Customer.external_customer_id == "13085")
        )
        assert str(repeat_customer.first_purchase_at) == "2009-12-01 07:45:00"
        assert str(repeat_customer.last_purchase_at) == "2010-04-01 08:00:00"

        return_only_customer = session.scalar(
            select(Customer).where(Customer.external_customer_id == "16321")
        )
        assert return_only_customer.first_purchase_at is None
        assert str(return_only_customer.first_seen_at) == "2009-12-01 10:33:00"


def test_same_source_can_be_loaded_into_another_workspace(tmp_path: Path) -> None:
    purchases, returns = _prepared_sample(tmp_path)
    engine = build_engine(f"sqlite+pysqlite:///{tmp_path / 'tenant.sqlite'}")
    upgrade_database(str(engine.url))

    first = load_processed_data(engine, purchases, returns, workspace_slug="retailer-a")
    second = load_processed_data(engine, purchases, returns, workspace_slug="retailer-b")

    assert first.workspace_id != second.workspace_id
    with session_scope(engine) as session:
        assert session.scalar(select(func.count(OrderItem.id))) == 18
