from pathlib import Path

import pandas as pd

from growthpilot.ml.common import load_artifact
from growthpilot.ml.segmentation import score_segments, train_segmentation


def feature_frame() -> pd.DataFrame:
    rows = []
    for index in range(30):
        group = index // 10
        rows.append(
            {
                "customer_id": index + 1,
                "recency_days": [5, 45, 180][group] + index % 3,
                "frequency_orders": [25, 9, 2][group] + index % 2,
                "monetary_value": [6000, 1800, 180][group] + index,
                "unique_products": [18, 9, 2][group],
                "customer_tenure_days": [700, 400, 200][group],
            }
        )
    return pd.DataFrame(rows)


def test_segmentation_selects_and_scores_clusters(tmp_path: Path):
    frame = feature_frame()
    path = tmp_path / "segmentation.joblib"
    result = train_segmentation(frame, path, min_k=3, max_k=5)
    assert 3 <= result["metadata"]["selected_k"] <= 5
    assert result["metadata"]["stability"] >= 0
    assert result["assignments"]["segment_name"].notna().all()
    rescored = score_segments(frame, load_artifact(path))
    assert len(rescored) == len(frame)
