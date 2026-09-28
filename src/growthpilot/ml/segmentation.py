from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import adjusted_rand_score, silhouette_score
from sklearn.preprocessing import RobustScaler

from growthpilot.ml.common import save_artifact, utc_now

SEGMENT_FEATURES = [
    "recency_days",
    "frequency_orders",
    "monetary_value",
    "unique_products",
    "customer_tenure_days",
]


def _matrix(frame: pd.DataFrame) -> pd.DataFrame:
    values = (
        frame[SEGMENT_FEATURES]
        .apply(pd.to_numeric, errors="coerce")
        .fillna(0)
        .astype(float)
        .clip(lower=0)
    )
    for column in ["frequency_orders", "monetary_value", "unique_products", "customer_tenure_days"]:
        values[column] = np.log1p(values[column])
    return values


def _stability(matrix: np.ndarray, labels: np.ndarray, k: int) -> float:
    scores: list[float] = []
    for seed in (7, 19, 31):
        candidate = KMeans(n_clusters=k, n_init=20, random_state=seed).fit_predict(matrix)
        scores.append(adjusted_rand_score(labels, candidate))
    return float(np.mean(scores))


def _name_clusters(frame: pd.DataFrame) -> dict[int, str]:
    profile = frame.groupby("cluster_id").agg(
        recency=("recency_days", "median"),
        frequency=("frequency_orders", "median"),
        value=("monetary_value", "median"),
    )
    names: dict[int, str] = {}
    high_value = profile["value"].rank(pct=True)
    high_frequency = profile["frequency"].rank(pct=True)
    recent = profile["recency"].rank(pct=True, ascending=False)
    for cluster in profile.index:
        value, frequency, freshness = high_value[cluster], high_frequency[cluster], recent[cluster]
        if value >= 0.75 and frequency >= 0.6 and freshness >= 0.55:
            name = "Champions"
        elif value >= 0.65 and freshness < 0.45:
            name = "High-Value At Risk"
        elif freshness >= 0.7 and frequency < 0.5:
            name = "New Customers"
        elif frequency >= 0.65 and freshness >= 0.45:
            name = "Loyal Customers"
        elif freshness < 0.3 and frequency < 0.45:
            name = "Dormant Customers"
        else:
            name = "Potential Loyalists"
        if name in names.values():
            name = f"{name} {int(cluster) + 1}"
        names[int(cluster)] = name
    return names


def train_segmentation(
    frame: pd.DataFrame, artifact_path: Path, *, min_k: int = 3, max_k: int = 8
) -> dict[str, Any]:
    if len(frame) < min_k * 3:
        raise ValueError("At least nine customer rows are required for segmentation")
    raw = _matrix(frame)
    scaler = RobustScaler().fit(raw)
    matrix = scaler.transform(raw)
    candidates: list[dict[str, Any]] = []
    upper = min(max_k, len(frame) - 1)
    for k in range(min_k, upper + 1):
        model = KMeans(n_clusters=k, n_init=30, random_state=42).fit(matrix)
        silhouette = float(silhouette_score(matrix, model.labels_))
        stability = _stability(matrix, model.labels_, k)
        candidates.append(
            {
                "k": k,
                "silhouette": silhouette,
                "stability": stability,
                "score": 0.7 * silhouette + 0.3 * stability,
            }
        )
    selected = max(candidates, key=lambda item: item["score"])
    model = KMeans(n_clusters=selected["k"], n_init=50, random_state=42).fit(matrix)
    assignments = frame.copy()
    assignments["cluster_id"] = model.labels_
    names = _name_clusters(assignments)
    assignments["segment_name"] = assignments["cluster_id"].map(names)
    assignments["distance_to_centroid"] = np.min(model.transform(matrix), axis=1)
    profiles = (
        assignments.groupby(["cluster_id", "segment_name"])[SEGMENT_FEATURES]
        .median()
        .reset_index()
        .to_dict(orient="records")
    )
    metadata = {
        "model_type": "segmentation",
        "version": "segmentation-v1",
        "trained_at": utc_now(),
        "features": SEGMENT_FEATURES,
        "selected_k": selected["k"],
        "silhouette": round(selected["silhouette"], 6),
        "stability": round(selected["stability"], 6),
        "candidates": candidates,
        "cluster_names": names,
        "profiles": profiles,
    }
    save_artifact(
        {"model": model, "scaler": scaler, "features": SEGMENT_FEATURES, "cluster_names": names},
        artifact_path,
        metadata,
    )
    return {
        "metadata": metadata,
        "assignments": assignments[
            ["customer_id", "cluster_id", "segment_name", "distance_to_centroid"]
        ],
    }


def score_segments(frame: pd.DataFrame, artifact: dict[str, Any]) -> pd.DataFrame:
    matrix = artifact["scaler"].transform(_matrix(frame))
    labels = artifact["model"].predict(matrix)
    return pd.DataFrame(
        {
            "customer_id": frame["customer_id"].to_numpy(),
            "cluster_id": labels,
            "segment_name": [artifact["cluster_names"][int(value)] for value in labels],
            "distance_to_centroid": np.min(artifact["model"].transform(matrix), axis=1),
        }
    )
