from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from growthpilot.ml.common import (
    MODEL_FEATURES,
    ModelArtifact,
    best_f1_threshold,
    build_classifier,
    classification_metrics,
    global_feature_explanations,
    model_version,
    save_artifact,
    utc_now,
)


def _split_temporally(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    dates = sorted(pd.to_datetime(frame["snapshot_date"]).unique())
    if len(dates) < 3:
        raise ValueError(
            "At least three distinct snapshot dates are required for temporal evaluation"
        )
    train_end = dates[max(0, int(len(dates) * 0.6) - 1)]
    validation_end = dates[max(1, int(len(dates) * 0.8) - 1)]
    train = frame[pd.to_datetime(frame["snapshot_date"]).le(train_end)]
    validation = frame[
        pd.to_datetime(frame["snapshot_date"]).gt(train_end)
        & pd.to_datetime(frame["snapshot_date"]).le(validation_end)
    ]
    test = frame[pd.to_datetime(frame["snapshot_date"]).gt(validation_end)]
    if min(len(train), len(validation), len(test)) == 0:
        raise ValueError("Temporal split produced an empty partition")
    return train, validation, test


def train_binary_model(
    frame: pd.DataFrame, *, label: str, model_type: str, artifact_path: Path
) -> ModelArtifact:
    train, validation, test = _split_temporally(frame)
    if train[label].nunique() < 2:
        raise ValueError(f"Training partition for {model_type} contains only one class")
    model = build_classifier()
    model.fit(train[MODEL_FEATURES], train[label])
    validation_probability = model.predict_proba(validation[MODEL_FEATURES])[:, 1]
    threshold = best_f1_threshold(validation[label], validation_probability)
    test_probability = model.predict_proba(test[MODEL_FEATURES])[:, 1]
    metrics: dict[str, Any] = {
        "validation": classification_metrics(validation[label], validation_probability, threshold),
        "test": classification_metrics(test[label], test_probability, threshold),
        "split": {
            "train_rows": len(train),
            "validation_rows": len(validation),
            "test_rows": len(test),
            "train_through": str(pd.to_datetime(train["snapshot_date"]).max()),
            "validation_through": str(pd.to_datetime(validation["snapshot_date"]).max()),
            "test_through": str(pd.to_datetime(test["snapshot_date"]).max()),
        },
        "global_explanations": global_feature_explanations(model, train, train[label]),
    }
    version = model_version(model_type)
    trained_at = utc_now()
    payload = {
        "model": model,
        "threshold": threshold,
        "features": MODEL_FEATURES,
        "model_type": model_type,
        "version": version,
    }
    metadata = {
        "model_type": model_type,
        "version": version,
        "trained_at": trained_at,
        "features": MODEL_FEATURES,
        "metrics": metrics,
    }
    save_artifact(payload, artifact_path, metadata)
    return ModelArtifact(model_type, version, artifact_path, metrics, MODEL_FEATURES, trained_at)


def train_supervised_models(frame: pd.DataFrame, artifact_dir: Path) -> dict[str, ModelArtifact]:
    return {
        "churn": train_binary_model(
            frame,
            label="churn_label",
            model_type="churn",
            artifact_path=artifact_dir / "churn.joblib",
        ),
        "propensity": train_binary_model(
            frame,
            label="propensity_label",
            model_type="propensity",
            artifact_path=artifact_dir / "propensity.joblib",
        ),
    }


def score_binary_model(frame: pd.DataFrame, artifact: dict[str, Any]) -> pd.DataFrame:
    probability = artifact["model"].predict_proba(frame[artifact["features"]])[:, 1]
    return pd.DataFrame(
        {
            "customer_id": frame["customer_id"],
            "score": probability,
            "predicted_label": probability >= artifact["threshold"],
        }
    )
