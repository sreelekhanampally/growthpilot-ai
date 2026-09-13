"""Create normalized retail transaction schema.

Revision ID: 20260913_0001
Revises: None
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260913_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bigint_pk = sa.BigInteger().with_variant(sa.Integer(), "sqlite")
    op.create_table(
        "workspaces",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.String(64), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workspaces")),
        sa.UniqueConstraint("slug", name=op.f("uq_workspaces_slug")),
    )
    op.create_table(
        "data_imports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("source_name", sa.String(255), nullable=False),
        sa.Column("purchases_sha256", sa.String(64), nullable=False),
        sa.Column("returns_sha256", sa.String(64), nullable=False),
        sa.Column("dataset_fingerprint", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("purchase_rows", sa.BigInteger(), nullable=False),
        sa.Column("return_rows", sa.BigInteger(), nullable=False),
        sa.Column("loaded_rows", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "status IN ('running', 'succeeded', 'failed')",
            name=op.f("ck_data_imports_valid_status"),
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_data_imports_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_data_imports")),
        sa.UniqueConstraint(
            "workspace_id", "dataset_fingerprint", name=op.f("uq_data_imports_workspace_id")
        ),
    )
    op.create_index(
        "ix_data_imports_workspace_created", "data_imports", ["workspace_id", "created_at"]
    )
    op.create_table(
        "customers",
        sa.Column("id", bigint_pk, autoincrement=True, nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("external_customer_id", sa.String(64), nullable=False),
        sa.Column("country", sa.String(96), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.Column("first_purchase_at", sa.DateTime()),
        sa.Column("last_purchase_at", sa.DateTime()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_customers_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_customers")),
        sa.UniqueConstraint(
            "workspace_id", "external_customer_id", name=op.f("uq_customers_workspace_id")
        ),
    )
    op.create_index(
        "ix_customers_workspace_last_purchase", "customers", ["workspace_id", "last_purchase_at"]
    )
    op.create_table(
        "products",
        sa.Column("id", bigint_pk, autoincrement=True, nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("stock_code", sa.String(64), nullable=False),
        sa.Column("description", sa.String(512)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_products_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_products")),
        sa.UniqueConstraint("workspace_id", "stock_code", name=op.f("uq_products_workspace_id")),
    )
    op.create_table(
        "orders",
        sa.Column("id", bigint_pk, autoincrement=True, nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("customer_id", sa.BigInteger(), nullable=False),
        sa.Column("invoice_no", sa.String(64), nullable=False),
        sa.Column("order_type", sa.String(16), nullable=False),
        sa.Column("invoice_date", sa.DateTime(), nullable=False),
        sa.Column("country", sa.String(96), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "order_type IN ('purchase', 'return')", name=op.f("ck_orders_valid_order_type")
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.id"],
            name=op.f("fk_orders_customer_id_customers"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_orders_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_orders")),
        sa.UniqueConstraint(
            "workspace_id", "invoice_no", "order_type", name=op.f("uq_orders_workspace_id")
        ),
    )
    op.create_index("ix_orders_customer_date", "orders", ["customer_id", "invoice_date"])
    op.create_index("ix_orders_workspace_date", "orders", ["workspace_id", "invoice_date"])
    op.create_table(
        "order_items",
        sa.Column("id", bigint_pk, autoincrement=True, nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.BigInteger(), nullable=False),
        sa.Column("product_id", sa.BigInteger(), nullable=False),
        sa.Column("data_import_id", sa.Uuid(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(14, 4), nullable=False),
        sa.Column("line_amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("source_row_id", sa.String(24), nullable=False),
        sa.Column("source_file", sa.String(255), nullable=False),
        sa.Column("source_sheet", sa.String(128), nullable=False),
        sa.Column("source_row_number", sa.BigInteger(), nullable=False),
        sa.CheckConstraint(
            "line_amount = round(quantity * unit_price, 4)",
            name=op.f("ck_order_items_valid_line_amount"),
        ),
        sa.CheckConstraint("quantity <> 0", name=op.f("ck_order_items_nonzero_quantity")),
        sa.CheckConstraint("unit_price >= 0", name=op.f("ck_order_items_nonnegative_unit_price")),
        sa.ForeignKeyConstraint(
            ["data_import_id"],
            ["data_imports.id"],
            name=op.f("fk_order_items_data_import_id_data_imports"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name=op.f("fk_order_items_order_id_orders"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_order_items_product_id_products"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_order_items_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_order_items")),
        sa.UniqueConstraint(
            "workspace_id", "source_row_id", name=op.f("uq_order_items_workspace_id")
        ),
    )
    op.create_index("ix_order_items_import", "order_items", ["data_import_id"])
    op.create_index("ix_order_items_product", "order_items", ["product_id"])


def downgrade() -> None:
    op.drop_index("ix_order_items_product", table_name="order_items")
    op.drop_index("ix_order_items_import", table_name="order_items")
    op.drop_table("order_items")
    op.drop_index("ix_orders_workspace_date", table_name="orders")
    op.drop_index("ix_orders_customer_date", table_name="orders")
    op.drop_table("orders")
    op.drop_table("products")
    op.drop_index("ix_customers_workspace_last_purchase", table_name="customers")
    op.drop_table("customers")
    op.drop_index("ix_data_imports_workspace_created", table_name="data_imports")
    op.drop_table("data_imports")
    op.drop_table("workspaces")
