from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

MODEL_FEATURES = [
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
]


@dataclass(frozen=True)
class ModelArtifact:
    model_type: str
    version: str
    path: Path
    metrics: dict[str, Any]
    feature_names: list[str]
    trained_at: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "model_type": self.model_type,
            "version": self.version,
            "path": str(self.path),
            "metrics": self.metrics,
            "feature_names": self.feature_names,
            "trained_at": self.trained_at,
        }


def _classifier(random_state: int = 42):
    try:
        from xgboost import XGBClassifier

        return XGBClassifier(
            n_estimators=300,
            max_depth=4,
            learning_rate=0.04,
            subsample=0.85,
            colsample_bytree=0.85,
            min_child_weight=3,
            reg_lambda=2.0,
            objective="binary:logistic",
            eval_metric="logloss",
            random_state=random_state,
            n_jobs=2,
        )
    except ImportError:
        return HistGradientBoostingClassifier(
            learning_rate=0.05,
            max_iter=250,
            max_leaf_nodes=31,
            l2_regularization=1.0,
            class_weight="balanced",
            random_state=random_state,
        )


def build_classifier(random_state: int = 42) -> Pipeline:
    preprocessing = ColumnTransformer(
        [
            (
                "numeric",
                Pipeline(
                    [("imputer", SimpleImputer(strategy="median")), ("scale", StandardScaler())]
                ),
                MODEL_FEATURES,
            )
        ],
        remainder="drop",
    )
    return Pipeline([("preprocess", preprocessing), ("model", _classifier(random_state))])


def classification_metrics(
    y_true: pd.Series, probability: np.ndarray, threshold: float
) -> dict[str, Any]:
    predicted = probability >= threshold
    metrics: dict[str, Any] = {
        "threshold": round(float(threshold), 6),
        "f1": round(float(f1_score(y_true, predicted, zero_division=0)), 6),
        "precision": round(float(precision_score(y_true, predicted, zero_division=0)), 6),
        "recall": round(float(recall_score(y_true, predicted, zero_division=0)), 6),
        "confusion_matrix": confusion_matrix(y_true, predicted, labels=[0, 1]).tolist(),
        "support": int(len(y_true)),
        "positive_rate": round(float(np.mean(y_true)), 6),
    }
    if pd.Series(y_true).nunique() > 1:
        metrics["roc_auc"] = round(float(roc_auc_score(y_true, probability)), 6)
        metrics["pr_auc"] = round(float(average_precision_score(y_true, probability)), 6)
    else:
        metrics["roc_auc"] = None
        metrics["pr_auc"] = None
    return metrics


def best_f1_threshold(y_true: pd.Series, probability: np.ndarray) -> float:
    candidates = np.linspace(0.1, 0.9, 81)
    scores = [f1_score(y_true, probability >= value, zero_division=0) for value in candidates]
    return float(candidates[int(np.argmax(scores))])


def save_artifact(payload: dict[str, Any], path: Path, metadata: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(payload, path)
    path.with_suffix(".json").write_text(json.dumps(metadata, indent=2, default=str) + "\n")


def load_artifact(path: Path) -> dict[str, Any]:
    return joblib.load(path)


def model_version(model_type: str) -> str:
    return f"{model_type}-v1"


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def global_feature_explanations(
    model: Pipeline, frame: pd.DataFrame, labels: pd.Series, top_k: int = 5
) -> list[dict[str, float | str]]:
    estimator = model.named_steps["model"]
    importances = getattr(estimator, "feature_importances_", None)
    if importances is None:
        sample = frame.sample(min(len(frame), 800), random_state=42)
        result = permutation_importance(
            model,
            sample[MODEL_FEATURES],
            labels.loc[sample.index],
            scoring="roc_auc",
            n_repeats=3,
            random_state=42,
        )
        importances = result.importances_mean
    ranked = sorted(
        zip(MODEL_FEATURES, importances, strict=True), key=lambda item: item[1], reverse=True
    )
    return [
        {"feature": name, "importance": round(float(value), 6)} for name, value in ranked[:top_k]
    ]
