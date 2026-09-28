from growthpilot.cli import _database_is_ready, _local_demo_database_url
from growthpilot.db.migrate import upgrade_database
from growthpilot.db.models import Workspace
from growthpilot.db.session import build_engine, session_scope


def test_local_database_readiness_detects_deleted_and_uninitialized_database(tmp_path):
    database_path = tmp_path / "growthpilot.db"
    database_url = f"sqlite+pysqlite:///{database_path}"

    assert _database_is_ready(database_url) is False
    assert database_path.exists() is False

    upgrade_database(database_url)
    assert _database_is_ready(database_url) is False

    engine = build_engine(database_url)
    with session_scope(engine) as session:
        session.add(Workspace(slug="demo-retail", name="Demo Retail", currency="GBP"))
    engine.dispose()

    assert _database_is_ready(database_url) is True


def test_local_demo_database_url_points_to_project_database():
    assert _local_demo_database_url().endswith("/growthpilot.db")
