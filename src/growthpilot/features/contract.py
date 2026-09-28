from datetime import datetime

import numpy as np
import pandas as pd

DEFAULT_FEATURE_VERSION = "customer-features-v1"
FEATURE_CONTRACT_VERSION = "growthpilot-feature-contract-v1"

FEATURE_COLUMNS = [
    "customer_id",
    "external_customer_id",
    "as_of",
    "feature_version",
    "first_purchase_at",
    "last_purchase_at",
    "recency_days",
    "frequency_orders",
    "monetary_value",
    "net_revenue",
    "total_items",
    "unique_products",
    "average_order_value",
    "average_basket_size",
    "customer_tenure_days",
    "purchase_interval_mean_days",
    "purchase_interval_std_days",
    "orders_30d",
    "orders_90d",
    "orders_180d",
    "revenue_30d",
    "revenue_90d",
    "revenue_180d",
    "orders_previous_30d",
    "revenue_previous_30d",
    "purchase_frequency_change_30d",
    "revenue_growth_30d",
    "return_orders",
    "returned_value",
    "cancellation_rate",
    "return_value_rate",
    "rfm_recency_score",
    "rfm_frequency_score",
    "rfm_monetary_score",
    "rfm_total_score",
    "rfm_code",
]


class FeatureContractError(ValueError):
    """Raised when generated features violate the versioned feature contract."""


def parse_as_of(value: str | datetime | pd.Timestamp) -> datetime:
    timestamp = pd.Timestamp(value)
    if pd.isna(timestamp):
        raise FeatureContractError("as_of must be a valid timestamp")
    if timestamp.tzinfo is not None:
        timestamp = timestamp.tz_convert("UTC").tz_localize(None)
    return timestamp.to_pydatetime()


def validate_feature_frame(frame: pd.DataFrame, as_of: datetime) -> None:
    missing = [column for column in FEATURE_COLUMNS if column not in frame.columns]
    if missing:
        raise FeatureContractError(f"Missing feature columns: {', '.join(missing)}")
    if frame.empty:
        raise FeatureContractError("No purchase-eligible customers exist at this cutoff")
    if frame["customer_id"].duplicated().any():
        raise FeatureContractError("Feature frame contains duplicate customers")
    if frame["last_purchase_at"].gt(pd.Timestamp(as_of)).any():
        raise FeatureContractError("A feature row contains future purchase information")

    nonnegative = [
        "recency_days",
        "monetary_value",
        "total_items",
        "unique_products",
        "average_order_value",
        "average_basket_size",
        "customer_tenure_days",
        "orders_30d",
        "orders_90d",
        "orders_180d",
        "revenue_30d",
        "revenue_90d",
        "revenue_180d",
        "orders_previous_30d",
        "revenue_previous_30d",
        "return_orders",
        "returned_value",
        "cancellation_rate",
        "return_value_rate",
    ]
    if (frame[nonnegative] < 0).any().any():
        raise FeatureContractError("A nonnegative feature contains a negative value")
    if frame["frequency_orders"].le(0).any():
        raise FeatureContractError("Every feature row must contain at least one purchase")
    if not (
        frame["orders_30d"].le(frame["orders_90d"])
        & frame["orders_90d"].le(frame["orders_180d"])
        & frame["orders_180d"].le(frame["frequency_orders"])
    ).all():
        raise FeatureContractError("Order windows are not monotonic")
    if not (
        frame["revenue_30d"].le(frame["revenue_90d"] + 1e-8)
        & frame["revenue_90d"].le(frame["revenue_180d"] + 1e-8)
        & frame["revenue_180d"].le(frame["monetary_value"] + 1e-8)
    ).all():
        raise FeatureContractError("Revenue windows are not monotonic")
    if frame["cancellation_rate"].gt(1).any():
        raise FeatureContractError("Cancellation rate cannot exceed 1")

    score_columns = ["rfm_recency_score", "rfm_frequency_score", "rfm_monetary_score"]
    if not frame[score_columns].isin(range(1, 6)).all().all():
        raise FeatureContractError("RFM component scores must be between 1 and 5")
    expected_code = (
        frame["rfm_recency_score"].astype(str)
        + frame["rfm_frequency_score"].astype(str)
        + frame["rfm_monetary_score"].astype(str)
    )
    if not expected_code.equals(frame["rfm_code"]):
        raise FeatureContractError("RFM code does not match component scores")

    numeric = frame.select_dtypes(include=["number"])
    if np.isinf(numeric.to_numpy(dtype=float)).any():
        raise FeatureContractError("Feature frame contains an infinite value")
