"""Add model, recommendation, action, and copilot persistence.

Revision ID: 20260920_0003
Revises: 20260916_0002
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260920_0003"
down_revision: str | None = "20260916_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bigint_pk = sa.BigInteger().with_variant(sa.Integer(), "sqlite")
    op.create_table(
        "model_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.Uuid(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("model_type", sa.String(32), nullable=False),
        sa.Column("version", sa.String(64), nullable=False),
        sa.Column("artifact_path", sa.String(512), nullable=False),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("feature_names", sa.JSON(), nullable=False),
        sa.Column("trained_from", sa.DateTime()),
        sa.Column("trained_through", sa.DateTime()),
        sa.Column("is_approved", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "model_type IN ('segmentation', 'churn', 'propensity', 'recommender')",
            name="ck_model_runs_valid_model_type",
        ),
    )
    op.create_index(
        "ix_model_runs_workspace_type", "model_runs", ["workspace_id", "model_type", "created_at"]
    )
    op.create_table(
        "customer_segments",
        sa.Column("id", bigint_pk, primary_key=True, autoincrement=True),
        sa.Column(
            "workspace_id",
            sa.Uuid(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "customer_id",
            sa.BigInteger(),
            sa.ForeignKey("customers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "model_run_id",
            sa.Uuid(),
            sa.ForeignKey("model_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("as_of", sa.DateTime(), nullable=False),
        sa.Column("cluster_id", sa.Integer(), nullable=False),
        sa.Column("segment_name", sa.String(64), nullable=False),
        sa.Column("distance_to_centroid", sa.Float(), nullable=False),
        sa.UniqueConstraint("model_run_id", "customer_id"),
    )
    op.create_index(
        "ix_segments_workspace_name", "customer_segments", ["workspace_id", "segment_name"]
    )
    op.create_table(
        "model_scores",
        sa.Column("id", bigint_pk, primary_key=True, autoincrement=True),
        sa.Column(
            "workspace_id",
            sa.Uuid(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "customer_id",
            sa.BigInteger(),
            sa.ForeignKey("customers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "model_run_id",
            sa.Uuid(),
            sa.ForeignKey("model_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("score_type", sa.String(24), nullable=False),
        sa.Column("as_of", sa.DateTime(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("predicted_label", sa.Boolean(), nullable=False),
        sa.Column("explanation", sa.JSON(), nullable=False),
        sa.CheckConstraint(
            "score_type IN ('churn', 'propensity')", name="ck_model_scores_valid_score_type"
        ),
        sa.UniqueConstraint("model_run_id", "customer_id", "score_type"),
    )
    op.create_index(
        "ix_model_scores_workspace_type_score",
        "model_scores",
        ["workspace_id", "score_type", "score"],
    )
    op.create_table(
        "product_recommendations",
        sa.Column("id", bigint_pk, primary_key=True, autoincrement=True),
        sa.Column(
            "workspace_id",
            sa.Uuid(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "customer_id",
            sa.BigInteger(),
            sa.ForeignKey("customers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "product_id",
            sa.BigInteger(),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "model_run_id",
            sa.Uuid(),
            sa.ForeignKey("model_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("as_of", sa.DateTime(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("reason", sa.String(512), nullable=False),
        sa.UniqueConstraint("model_run_id", "customer_id", "product_id"),
    )
    op.create_index(
        "ix_recommendations_customer_rank", "product_recommendations", ["customer_id", "rank"]
    )
    op.create_table(
        "customer_actions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.Uuid(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "customer_id",
            sa.BigInteger(),
            sa.ForeignKey("customers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("action_type", sa.String(64), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("priority_score", sa.Float(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("outcome", sa.String(64)),
        sa.Column("outcome_value", sa.Numeric(18, 4)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "ix_actions_workspace_status", "customer_actions", ["workspace_id", "status", "created_at"]
    )
    op.create_table(
        "knowledge_documents",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.Uuid(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("source", sa.String(512), nullable=False),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_table(
        "document_chunks",
        sa.Column("id", bigint_pk, primary_key=True, autoincrement=True),
        sa.Column(
            "document_id",
            sa.Uuid(),
            sa.ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", sa.JSON()),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
    )
    op.create_index(
        "ix_document_chunks_document", "document_chunks", ["document_id", "chunk_index"]
    )
    op.create_table(
        "copilot_conversations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.Uuid(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_table(
        "copilot_messages",
        sa.Column("id", bigint_pk, primary_key=True, autoincrement=True),
        sa.Column(
            "conversation_id",
            sa.Uuid(),
            sa.ForeignKey("copilot_conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("citations", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index(
        "ix_copilot_messages_conversation", "copilot_messages", ["conversation_id", "created_at"]
    )


def downgrade() -> None:
    for index, table in [
        ("ix_copilot_messages_conversation", "copilot_messages"),
        ("ix_document_chunks_document", "document_chunks"),
        ("ix_actions_workspace_status", "customer_actions"),
        ("ix_recommendations_customer_rank", "product_recommendations"),
        ("ix_model_scores_workspace_type_score", "model_scores"),
        ("ix_segments_workspace_name", "customer_segments"),
        ("ix_model_runs_workspace_type", "model_runs"),
    ]:
        op.drop_index(index, table_name=table)
    for table in [
        "copilot_messages",
        "copilot_conversations",
        "document_chunks",
        "knowledge_documents",
        "customer_actions",
        "product_recommendations",
        "model_scores",
        "customer_segments",
        "model_runs",
    ]:
        op.drop_table(table)
