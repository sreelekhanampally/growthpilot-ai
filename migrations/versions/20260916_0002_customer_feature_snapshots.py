"""Add versioned customer feature snapshots.

Revision ID: 20260916_0002
Revises: 20260913_0001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260916_0002"
down_revision: str | None = "20260913_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bigint_pk = sa.BigInteger().with_variant(sa.Integer(), "sqlite")
    op.create_index("ix_order_items_order", "order_items", ["order_id"])
    op.create_table(
        "feature_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("as_of", sa.DateTime(), nullable=False),
        sa.Column("feature_version", sa.String(64), nullable=False),
        sa.Column("source_fingerprint", sa.String(64), nullable=False),
        sa.Column("customer_count", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_feature_runs_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_feature_runs")),
        sa.UniqueConstraint(
            "workspace_id",
            "as_of",
            "feature_version",
            name=op.f("uq_feature_runs_workspace_id"),
        ),
    )
    op.create_index("ix_feature_runs_workspace_as_of", "feature_runs", ["workspace_id", "as_of"])
    op.create_table(
        "customer_feature_snapshots",
        sa.Column("id", bigint_pk, autoincrement=True, nullable=False),
        sa.Column("feature_run_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("customer_id", sa.BigInteger(), nullable=False),
        sa.Column("as_of", sa.DateTime(), nullable=False),
        sa.Column("feature_version", sa.String(64), nullable=False),
        sa.Column("first_purchase_at", sa.DateTime(), nullable=False),
        sa.Column("last_purchase_at", sa.DateTime(), nullable=False),
        sa.Column("recency_days", sa.Integer(), nullable=False),
        sa.Column("frequency_orders", sa.Integer(), nullable=False),
        sa.Column("monetary_value", sa.Numeric(18, 4), nullable=False),
        sa.Column("net_revenue", sa.Numeric(18, 4), nullable=False),
        sa.Column("total_items", sa.BigInteger(), nullable=False),
        sa.Column("unique_products", sa.Integer(), nullable=False),
        sa.Column("average_order_value", sa.Numeric(18, 4), nullable=False),
        sa.Column("average_basket_size", sa.Numeric(18, 4), nullable=False),
        sa.Column("customer_tenure_days", sa.Integer(), nullable=False),
        sa.Column("purchase_interval_mean_days", sa.Numeric(12, 4)),
        sa.Column("purchase_interval_std_days", sa.Numeric(12, 4)),
        sa.Column("orders_30d", sa.Integer(), nullable=False),
        sa.Column("orders_90d", sa.Integer(), nullable=False),
        sa.Column("orders_180d", sa.Integer(), nullable=False),
        sa.Column("revenue_30d", sa.Numeric(18, 4), nullable=False),
        sa.Column("revenue_90d", sa.Numeric(18, 4), nullable=False),
        sa.Column("revenue_180d", sa.Numeric(18, 4), nullable=False),
        sa.Column("orders_previous_30d", sa.Integer(), nullable=False),
        sa.Column("revenue_previous_30d", sa.Numeric(18, 4), nullable=False),
        sa.Column("purchase_frequency_change_30d", sa.Integer(), nullable=False),
        sa.Column("revenue_growth_30d", sa.Numeric(14, 6)),
        sa.Column("return_orders", sa.Integer(), nullable=False),
        sa.Column("returned_value", sa.Numeric(18, 4), nullable=False),
        sa.Column("cancellation_rate", sa.Numeric(8, 6), nullable=False),
        sa.Column("return_value_rate", sa.Numeric(14, 6), nullable=False),
        sa.Column("rfm_recency_score", sa.SmallInteger(), nullable=False),
        sa.Column("rfm_frequency_score", sa.SmallInteger(), nullable=False),
        sa.Column("rfm_monetary_score", sa.SmallInteger(), nullable=False),
        sa.Column("rfm_total_score", sa.SmallInteger(), nullable=False),
        sa.Column("rfm_code", sa.String(3), nullable=False),
        sa.CheckConstraint(
            "frequency_orders > 0", name=op.f("ck_customer_feature_snapshots_positive_frequency")
        ),
        sa.CheckConstraint(
            "monetary_value >= 0", name=op.f("ck_customer_feature_snapshots_nonnegative_monetary")
        ),
        sa.CheckConstraint(
            "recency_days >= 0", name=op.f("ck_customer_feature_snapshots_nonnegative_recency")
        ),
        sa.CheckConstraint(
            "rfm_frequency_score BETWEEN 1 AND 5",
            name=op.f("ck_customer_feature_snapshots_valid_f_score"),
        ),
        sa.CheckConstraint(
            "rfm_monetary_score BETWEEN 1 AND 5",
            name=op.f("ck_customer_feature_snapshots_valid_m_score"),
        ),
        sa.CheckConstraint(
            "rfm_recency_score BETWEEN 1 AND 5",
            name=op.f("ck_customer_feature_snapshots_valid_r_score"),
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.id"],
            name=op.f("fk_customer_feature_snapshots_customer_id_customers"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["feature_run_id"],
            ["feature_runs.id"],
            name=op.f("fk_customer_feature_snapshots_feature_run_id_feature_runs"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_customer_feature_snapshots_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_customer_feature_snapshots")),
        sa.UniqueConstraint(
            "feature_run_id",
            "customer_id",
            name=op.f("uq_customer_feature_snapshots_feature_run_id"),
        ),
        sa.UniqueConstraint(
            "workspace_id",
            "customer_id",
            "as_of",
            "feature_version",
            name=op.f("uq_customer_feature_snapshots_workspace_id"),
        ),
    )
    op.create_index(
        "ix_feature_snapshots_customer_as_of",
        "customer_feature_snapshots",
        ["customer_id", "as_of"],
    )
    op.create_index(
        "ix_feature_snapshots_workspace_as_of",
        "customer_feature_snapshots",
        ["workspace_id", "as_of"],
    )


def downgrade() -> None:
    op.drop_index("ix_feature_snapshots_workspace_as_of", table_name="customer_feature_snapshots")
    op.drop_index("ix_feature_snapshots_customer_as_of", table_name="customer_feature_snapshots")
    op.drop_table("customer_feature_snapshots")
    op.drop_index("ix_feature_runs_workspace_as_of", table_name="feature_runs")
    op.drop_table("feature_runs")
    op.drop_index("ix_order_items_order", table_name="order_items")
