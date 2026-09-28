from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from growthpilot.features.contract import FEATURE_COLUMNS, validate_feature_frame

TRANSACTION_COLUMNS = {
    "customer_id",
    "external_customer_id",
    "invoice_no",
    "order_type",
    "invoice_date",
    "product_id",
    "quantity",
    "line_amount",
}


def _rfm_score(series: pd.Series, *, higher_is_better: bool) -> pd.Series:
    ranks = series.rank(method="average", ascending=higher_is_better)
    midpoint_percentile = (ranks - 0.5) / len(series)
    return (np.floor(midpoint_percentile * 5) + 1).clip(1, 5).astype(int)


def _window(order_level: pd.DataFrame, start: datetime, end: datetime) -> pd.DataFrame:
    selected = order_level[
        order_level["invoice_date"].gt(pd.Timestamp(start))
        & order_level["invoice_date"].le(pd.Timestamp(end))
    ]
    if selected.empty:
        return pd.DataFrame(columns=["orders", "revenue"], dtype=float)
    return selected.groupby("customer_id").agg(
        orders=("invoice_no", "nunique"), revenue=("order_revenue", "sum")
    )


def _join_window(
    features: pd.DataFrame,
    order_level: pd.DataFrame,
    *,
    start: datetime,
    end: datetime,
    orders_column: str,
    revenue_column: str,
) -> None:
    window = _window(order_level, start, end)
    features[orders_column] = window["orders"].reindex(features.index).fillna(0).astype(int)
    features[revenue_column] = window["revenue"].reindex(features.index).fillna(0.0)


def build_customer_features(
    transactions: pd.DataFrame,
    *,
    as_of: datetime,
    feature_version: str,
) -> pd.DataFrame:
    missing = sorted(TRANSACTION_COLUMNS - set(transactions.columns))
    if missing:
        raise ValueError(f"Transaction frame is missing: {', '.join(missing)}")

    frame = transactions.copy()
    frame["invoice_date"] = pd.to_datetime(frame["invoice_date"], errors="coerce")
    frame["quantity"] = pd.to_numeric(frame["quantity"], errors="coerce")
    frame["line_amount"] = pd.to_numeric(frame["line_amount"], errors="coerce")
    frame = frame[
        frame["invoice_date"].notna()
        & frame["invoice_date"].le(pd.Timestamp(as_of))
        & frame["order_type"].isin(["purchase", "return"])
    ]

    purchases = frame[frame["order_type"].eq("purchase")].copy()
    if purchases.empty:
        raise ValueError("No purchase transactions exist at the requested cutoff")
    returns = frame[frame["order_type"].eq("return")].copy()

    order_level = (
        purchases.groupby(
            ["customer_id", "external_customer_id", "invoice_no", "invoice_date"],
            as_index=False,
        )
        .agg(
            order_revenue=("line_amount", "sum"),
            order_items=("quantity", "sum"),
            order_unique_products=("product_id", "nunique"),
        )
        .sort_values(["customer_id", "invoice_date", "invoice_no"])
    )

    features = order_level.groupby("customer_id").agg(
        external_customer_id=("external_customer_id", "first"),
        first_purchase_at=("invoice_date", "min"),
        last_purchase_at=("invoice_date", "max"),
        frequency_orders=("invoice_no", "nunique"),
        monetary_value=("order_revenue", "sum"),
        total_items=("order_items", "sum"),
        average_order_value=("order_revenue", "mean"),
        average_basket_size=("order_items", "mean"),
    )
    features["unique_products"] = (
        purchases.groupby("customer_id")["product_id"].nunique().reindex(features.index)
    )

    features["recency_days"] = (
        (pd.Timestamp(as_of) - features["last_purchase_at"]).dt.total_seconds() // 86_400
    ).astype(int)
    features["customer_tenure_days"] = (
        (pd.Timestamp(as_of) - features["first_purchase_at"]).dt.total_seconds() // 86_400
    ).astype(int)

    dated_orders = order_level[["customer_id", "invoice_no", "invoice_date"]].copy()
    dated_orders["purchase_interval_days"] = (
        dated_orders.groupby("customer_id")["invoice_date"].diff().dt.total_seconds() / 86_400
    )
    interval_groups = dated_orders.groupby("customer_id")["purchase_interval_days"]
    features["purchase_interval_mean_days"] = interval_groups.mean().reindex(features.index)
    features["purchase_interval_std_days"] = interval_groups.apply(
        lambda values: values.dropna().std(ddof=0) if values.notna().any() else np.nan
    ).reindex(features.index)

    for days in (30, 90, 180):
        _join_window(
            features,
            order_level,
            start=as_of - timedelta(days=days),
            end=as_of,
            orders_column=f"orders_{days}d",
            revenue_column=f"revenue_{days}d",
        )
    _join_window(
        features,
        order_level,
        start=as_of - timedelta(days=60),
        end=as_of - timedelta(days=30),
        orders_column="orders_previous_30d",
        revenue_column="revenue_previous_30d",
    )
    features["purchase_frequency_change_30d"] = (
        features["orders_30d"] - features["orders_previous_30d"]
    )
    features["revenue_growth_30d"] = np.where(
        features["revenue_previous_30d"].gt(0),
        (features["revenue_30d"] - features["revenue_previous_30d"])
        / features["revenue_previous_30d"],
        np.nan,
    )

    if returns.empty:
        return_metrics = pd.DataFrame(columns=["return_orders", "returned_value"])
    else:
        return_metrics = returns.groupby("customer_id").agg(
            return_orders=("invoice_no", "nunique"),
            returned_value=("line_amount", lambda values: -values.sum()),
        )
    features["return_orders"] = (
        return_metrics.get("return_orders", pd.Series(dtype=float))
        .reindex(features.index)
        .fillna(0)
        .astype(int)
    )
    features["returned_value"] = (
        return_metrics.get("returned_value", pd.Series(dtype=float))
        .reindex(features.index)
        .fillna(0.0)
        .clip(lower=0.0)
    )
    features["net_revenue"] = features["monetary_value"] - features["returned_value"]
    features["cancellation_rate"] = features["return_orders"] / (
        features["frequency_orders"] + features["return_orders"]
    )
    features["return_value_rate"] = np.where(
        features["monetary_value"].gt(0),
        features["returned_value"] / features["monetary_value"],
        0.0,
    )

    features["rfm_recency_score"] = _rfm_score(features["recency_days"], higher_is_better=False)
    features["rfm_frequency_score"] = _rfm_score(
        features["frequency_orders"], higher_is_better=True
    )
    features["rfm_monetary_score"] = _rfm_score(features["monetary_value"], higher_is_better=True)
    features["rfm_total_score"] = features[
        ["rfm_recency_score", "rfm_frequency_score", "rfm_monetary_score"]
    ].sum(axis=1)
    features["rfm_code"] = (
        features["rfm_recency_score"].astype(str)
        + features["rfm_frequency_score"].astype(str)
        + features["rfm_monetary_score"].astype(str)
    )
    features["as_of"] = pd.Timestamp(as_of)
    features["feature_version"] = feature_version

    result = features.reset_index()[FEATURE_COLUMNS]
    validate_feature_frame(result, as_of)
    return result.sort_values("customer_id").reset_index(drop=True)
