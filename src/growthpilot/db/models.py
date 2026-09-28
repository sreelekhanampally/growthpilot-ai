import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from growthpilot.db.base import Base

BIGINT_PK = BigInteger().with_variant(Integer, "sqlite")


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="GBP")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class DataImport(Base):
    __tablename__ = "data_imports"
    __table_args__ = (
        CheckConstraint("status IN ('running', 'succeeded', 'failed')", name="valid_status"),
        UniqueConstraint("workspace_id", "dataset_fingerprint"),
        Index("ix_data_imports_workspace_created", "workspace_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    purchases_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    returns_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    dataset_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="running")
    purchase_rows: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    return_rows: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    loaded_rows: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Customer(Base):
    __tablename__ = "customers"
    __table_args__ = (
        UniqueConstraint("workspace_id", "external_customer_id"),
        Index("ix_customers_workspace_last_purchase", "workspace_id", "last_purchase_at"),
    )

    id: Mapped[int] = mapped_column(BIGINT_PK, primary_key=True, autoincrement=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    external_customer_id: Mapped[str] = mapped_column(String(64), nullable=False)
    country: Mapped[str] = mapped_column(String(96), nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    first_purchase_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    last_purchase_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    orders: Mapped[list["Order"]] = relationship(back_populates="customer")


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (UniqueConstraint("workspace_id", "stock_code"),)

    id: Mapped[int] = mapped_column(BIGINT_PK, primary_key=True, autoincrement=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    stock_code: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint("order_type IN ('purchase', 'return')", name="valid_order_type"),
        UniqueConstraint("workspace_id", "invoice_no", "order_type"),
        Index("ix_orders_workspace_date", "workspace_id", "invoice_date"),
        Index("ix_orders_customer_date", "customer_id", "invoice_date"),
    )

    id: Mapped[int] = mapped_column(BIGINT_PK, primary_key=True, autoincrement=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False
    )
    invoice_no: Mapped[str] = mapped_column(String(64), nullable=False)
    order_type: Mapped[str] = mapped_column(String(16), nullable=False)
    invoice_date: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    country: Mapped[str] = mapped_column(String(96), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    customer: Mapped[Customer] = relationship(back_populates="orders")
    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )


class OrderItem(Base):
    __tablename__ = "order_items"
    __table_args__ = (
        CheckConstraint("quantity <> 0", name="nonzero_quantity"),
        CheckConstraint("unit_price >= 0", name="nonnegative_unit_price"),
        CheckConstraint("line_amount = round(quantity * unit_price, 4)", name="valid_line_amount"),
        UniqueConstraint("workspace_id", "source_row_id"),
        Index("ix_order_items_order", "order_id"),
        Index("ix_order_items_product", "product_id"),
        Index("ix_order_items_import", "data_import_id"),
    )

    id: Mapped[int] = mapped_column(BIGINT_PK, primary_key=True, autoincrement=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), nullable=False
    )
    data_import_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("data_imports.id", ondelete="RESTRICT"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    line_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    source_row_id: Mapped[str] = mapped_column(String(24), nullable=False)
    source_file: Mapped[str] = mapped_column(String(255), nullable=False)
    source_sheet: Mapped[str] = mapped_column(String(128), nullable=False)
    source_row_number: Mapped[int] = mapped_column(BigInteger, nullable=False)

    order: Mapped[Order] = relationship(back_populates="items")


class FeatureRun(Base):
    __tablename__ = "feature_runs"
    __table_args__ = (
        UniqueConstraint("workspace_id", "as_of", "feature_version"),
        Index("ix_feature_runs_workspace_as_of", "workspace_id", "as_of"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    feature_version: Mapped[str] = mapped_column(String(64), nullable=False)
    source_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    customer_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    snapshots: Mapped[list["CustomerFeatureSnapshot"]] = relationship(
        back_populates="feature_run", cascade="all, delete-orphan"
    )


class CustomerFeatureSnapshot(Base):
    __tablename__ = "customer_feature_snapshots"
    __table_args__ = (
        CheckConstraint("recency_days >= 0", name="nonnegative_recency"),
        CheckConstraint("frequency_orders > 0", name="positive_frequency"),
        CheckConstraint("monetary_value >= 0", name="nonnegative_monetary"),
        CheckConstraint("rfm_recency_score BETWEEN 1 AND 5", name="valid_r_score"),
        CheckConstraint("rfm_frequency_score BETWEEN 1 AND 5", name="valid_f_score"),
        CheckConstraint("rfm_monetary_score BETWEEN 1 AND 5", name="valid_m_score"),
        UniqueConstraint("feature_run_id", "customer_id"),
        UniqueConstraint("workspace_id", "customer_id", "as_of", "feature_version"),
        Index("ix_feature_snapshots_workspace_as_of", "workspace_id", "as_of"),
        Index("ix_feature_snapshots_customer_as_of", "customer_id", "as_of"),
    )

    id: Mapped[int] = mapped_column(BIGINT_PK, primary_key=True, autoincrement=True)
    feature_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("feature_runs.id", ondelete="CASCADE"), nullable=False
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"), nullable=False
    )
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    feature_version: Mapped[str] = mapped_column(String(64), nullable=False)

    first_purchase_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    last_purchase_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    recency_days: Mapped[int] = mapped_column(Integer, nullable=False)
    frequency_orders: Mapped[int] = mapped_column(Integer, nullable=False)
    monetary_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    net_revenue: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    total_items: Mapped[int] = mapped_column(BigInteger, nullable=False)
    unique_products: Mapped[int] = mapped_column(Integer, nullable=False)
    average_order_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    average_basket_size: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    customer_tenure_days: Mapped[int] = mapped_column(Integer, nullable=False)
    purchase_interval_mean_days: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    purchase_interval_std_days: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))

    orders_30d: Mapped[int] = mapped_column(Integer, nullable=False)
    orders_90d: Mapped[int] = mapped_column(Integer, nullable=False)
    orders_180d: Mapped[int] = mapped_column(Integer, nullable=False)
    revenue_30d: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    revenue_90d: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    revenue_180d: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    orders_previous_30d: Mapped[int] = mapped_column(Integer, nullable=False)
    revenue_previous_30d: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    purchase_frequency_change_30d: Mapped[int] = mapped_column(Integer, nullable=False)
    revenue_growth_30d: Mapped[Decimal | None] = mapped_column(Numeric(14, 6))

    return_orders: Mapped[int] = mapped_column(Integer, nullable=False)
    returned_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    cancellation_rate: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)
    return_value_rate: Mapped[Decimal] = mapped_column(Numeric(14, 6), nullable=False)

    rfm_recency_score: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    rfm_frequency_score: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    rfm_monetary_score: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    rfm_total_score: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    rfm_code: Mapped[str] = mapped_column(String(3), nullable=False)

    feature_run: Mapped[FeatureRun] = relationship(back_populates="snapshots")


class ModelRun(Base):
    __tablename__ = "model_runs"
    __table_args__ = (
        CheckConstraint(
            "model_type IN ('segmentation', 'churn', 'propensity', 'recommender')",
            name="valid_model_type",
        ),
        Index("ix_model_runs_workspace_type", "workspace_id", "model_type", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    model_type: Mapped[str] = mapped_column(String(32), nullable=False)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    artifact_path: Mapped[str] = mapped_column(String(512), nullable=False)
    parameters: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    metrics: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    feature_names: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    trained_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    trained_through: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    is_approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class CustomerSegment(Base):
    __tablename__ = "customer_segments"
    __table_args__ = (
        UniqueConstraint("model_run_id", "customer_id"),
        Index("ix_segments_workspace_name", "workspace_id", "segment_name"),
    )

    id: Mapped[int] = mapped_column(BIGINT_PK, primary_key=True, autoincrement=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"), nullable=False
    )
    model_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("model_runs.id", ondelete="CASCADE"), nullable=False
    )
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    cluster_id: Mapped[int] = mapped_column(Integer, nullable=False)
    segment_name: Mapped[str] = mapped_column(String(64), nullable=False)
    distance_to_centroid: Mapped[float] = mapped_column(Float, nullable=False)


class ModelScore(Base):
    __tablename__ = "model_scores"
    __table_args__ = (
        CheckConstraint("score_type IN ('churn', 'propensity')", name="valid_score_type"),
        UniqueConstraint("model_run_id", "customer_id", "score_type"),
        Index("ix_model_scores_workspace_type_score", "workspace_id", "score_type", "score"),
    )

    id: Mapped[int] = mapped_column(BIGINT_PK, primary_key=True, autoincrement=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"), nullable=False
    )
    model_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("model_runs.id", ondelete="CASCADE"), nullable=False
    )
    score_type: Mapped[str] = mapped_column(String(24), nullable=False)
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    predicted_label: Mapped[bool] = mapped_column(Boolean, nullable=False)
    explanation: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class ProductRecommendation(Base):
    __tablename__ = "product_recommendations"
    __table_args__ = (
        UniqueConstraint("model_run_id", "customer_id", "product_id"),
        Index("ix_recommendations_customer_rank", "customer_id", "rank"),
    )

    id: Mapped[int] = mapped_column(BIGINT_PK, primary_key=True, autoincrement=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    model_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("model_runs.id", ondelete="CASCADE"), nullable=False
    )
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    reason: Mapped[str] = mapped_column(String(512), nullable=False)


class CustomerAction(Base):
    __tablename__ = "customer_actions"
    __table_args__ = (Index("ix_actions_workspace_status", "workspace_id", "status", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"), nullable=False
    )
    action_type: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    priority_score: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="recommended")
    outcome: Mapped[str | None] = mapped_column(String(64))
    outcome_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    source: Mapped[str] = mapped_column(String(512), nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    __table_args__ = (Index("ix_document_chunks_document", "document_id", "chunk_index"),)
    id: Mapped[int] = mapped_column(BIGINT_PK, primary_key=True, autoincrement=True)
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_documents.id", ondelete="CASCADE"), nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list | None] = mapped_column(JSON)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class CopilotConversation(Base):
    __tablename__ = "copilot_conversations"
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="New conversation")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class CopilotMessage(Base):
    __tablename__ = "copilot_messages"
    __table_args__ = (Index("ix_copilot_messages_conversation", "conversation_id", "created_at"),)
    id: Mapped[int] = mapped_column(BIGINT_PK, primary_key=True, autoincrement=True)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("copilot_conversations.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    citations: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
