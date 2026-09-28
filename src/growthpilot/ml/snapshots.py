from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd

from growthpilot.features.builder import build_customer_features
from growthpilot.features.contract import DEFAULT_FEATURE_VERSION


def monthly_cutoffs(
    transactions: pd.DataFrame, *, history_days: int = 180, horizon_days: int = 90
) -> list[datetime]:
    dates = pd.to_datetime(transactions["invoice_date"])
    start = dates.min().normalize() + pd.Timedelta(days=history_days)
    end = dates.max().normalize() - pd.Timedelta(days=horizon_days)
    if start > end:
        return []
    return [timestamp.to_pydatetime() for timestamp in pd.date_range(start, end, freq="MS")]


def build_supervised_snapshots(
    transactions: pd.DataFrame,
    *,
    cutoffs: list[datetime] | None = None,
    churn_horizon_days: int = 90,
    propensity_horizon_days: int = 30,
) -> pd.DataFrame:
    frame = transactions.copy()
    frame["invoice_date"] = pd.to_datetime(frame["invoice_date"])
    selected_cutoffs = cutoffs or monthly_cutoffs(frame, horizon_days=churn_horizon_days)
    snapshots: list[pd.DataFrame] = []
    purchases = frame[frame["order_type"].eq("purchase")]
    for cutoff in selected_cutoffs:
        history = frame[frame["invoice_date"].le(pd.Timestamp(cutoff))]
        if history.empty:
            continue
        features = build_customer_features(
            history, as_of=cutoff, feature_version=DEFAULT_FEATURE_VERSION
        )
        future = purchases[
            purchases["invoice_date"].gt(pd.Timestamp(cutoff))
            & purchases["invoice_date"].le(
                pd.Timestamp(cutoff + timedelta(days=churn_horizon_days))
            )
        ]
        purchase_dates = future.groupby("customer_id")["invoice_date"].min()
        features["churn_label"] = (~features["customer_id"].isin(purchase_dates.index)).astype(int)
        propensity_deadline = pd.Timestamp(cutoff + timedelta(days=propensity_horizon_days))
        propensity_customers = purchase_dates[purchase_dates.le(propensity_deadline)].index
        features["propensity_label"] = (
            features["customer_id"].isin(propensity_customers).astype(int)
        )
        features["snapshot_date"] = pd.Timestamp(cutoff)
        snapshots.append(features)
    if not snapshots:
        raise ValueError("The transaction history is too short to create supervised snapshots")
    return pd.concat(snapshots, ignore_index=True).sort_values(["snapshot_date", "customer_id"])
