from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from growthpilot.db.base import Base
from growthpilot.db.models import Customer, Workspace
from growthpilot.services.intelligence import IntelligenceService


def test_numeric_external_customer_id_is_not_treated_only_as_internal_id():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        workspace = Workspace(slug="demo-retail", name="Demo Retail", currency="GBP")
        session.add(workspace)
        session.flush()
        session.add(
            Customer(
                workspace_id=workspace.id,
                external_customer_id="15000",
                country="United Kingdom",
                first_seen_at=datetime(2011, 1, 1),
                last_seen_at=datetime(2011, 2, 1),
                first_purchase_at=datetime(2011, 1, 1),
                last_purchase_at=datetime(2011, 2, 1),
            )
        )
        session.commit()

    result = IntelligenceService(engine).customer_360("15000")
    assert result["external_customer_id"] == "15000"
