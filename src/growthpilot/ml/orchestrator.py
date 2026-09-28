from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import Engine, desc, insert, select
from sqlalchemy.orm import Session

from growthpilot.db.models import (
    CustomerFeatureSnapshot,
    CustomerSegment,
    ModelRun,
    ModelScore,
    Order,
    OrderItem,
    ProductRecommendation,
    Workspace,
)
from growthpilot.db.session import session_scope
from growthpilot.ml.common import MODEL_FEATURES, load_artifact
from growthpilot.ml.segmentation import SEGMENT_FEATURES, train_segmentation
from growthpilot.ml.snapshots import build_supervised_snapshots
from growthpilot.ml.training import score_binary_model, train_supervised_models
from growthpilot.recommendations.engine import HybridRecommender


@dataclass(frozen=True)
class TrainingSummary:
    as_of: datetime
    customers: int
    supervised_rows: int
    artifacts: dict[str, str]
    metrics: dict[str, Any]


def _workspace(session: Session, slug: str) -> Workspace:
    row = session.scalar(select(Workspace).where(Workspace.slug == slug))
    if row is None:
        raise ValueError(f"Workspace does not exist: {slug}")
    return row


def _transactions(session: Session, workspace_id: uuid.UUID) -> pd.DataFrame:
    statement = (
        select(
            Order.customer_id,
            Order.invoice_no,
            Order.order_type,
            Order.invoice_date,
            OrderItem.product_id,
            OrderItem.quantity,
            OrderItem.line_amount,
        )
        .select_from(OrderItem)
        .join(Order, Order.id == OrderItem.order_id)
        .where(Order.workspace_id == workspace_id)
    )
    frame = pd.read_sql(statement, session.connection())
    frame["quantity"] = pd.to_numeric(frame["quantity"], errors="coerce")
    frame["line_amount"] = pd.to_numeric(frame["line_amount"], errors="coerce")
    frame["external_customer_id"] = frame["customer_id"].astype(str)
    return frame


def _latest_features(session: Session, workspace_id: uuid.UUID) -> tuple[datetime, pd.DataFrame]:
    as_of = session.scalar(
        select(CustomerFeatureSnapshot.as_of)
        .where(CustomerFeatureSnapshot.workspace_id == workspace_id)
        .order_by(desc(CustomerFeatureSnapshot.as_of))
        .limit(1)
    )
    if as_of is None:
        raise ValueError("Build a customer feature snapshot before training models")
    rows = (
        session.execute(
            select(CustomerFeatureSnapshot).where(
                CustomerFeatureSnapshot.workspace_id == workspace_id,
                CustomerFeatureSnapshot.as_of == as_of,
            )
        )
        .scalars()
        .all()
    )
    data = []
    for row in rows:
        record = {"customer_id": row.customer_id}
        for feature in sorted(set(MODEL_FEATURES + SEGMENT_FEATURES)):
            value = getattr(row, feature)
            record[feature] = float(value) if value is not None else None
        data.append(record)
    return as_of, pd.DataFrame(data)


def _add_run(
    session: Session,
    *,
    workspace_id: uuid.UUID,
    model_type: str,
    version: str,
    artifact_path: Path,
    parameters: dict,
    metrics: dict,
    features: list[str],
    trained_from: datetime | None,
    trained_through: datetime | None,
) -> ModelRun:
    run = ModelRun(
        workspace_id=workspace_id,
        model_type=model_type,
        version=version,
        artifact_path=str(artifact_path),
        parameters=parameters,
        metrics=metrics,
        feature_names=features,
        trained_from=trained_from,
        trained_through=trained_through,
        is_approved=True,
    )
    session.add(run)
    session.flush()
    return run


def train_all(
    engine: Engine, *, workspace_slug: str, artifact_dir: Path, training_output: Path | None = None
) -> TrainingSummary:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    with session_scope(engine) as session:
        workspace = _workspace(session, workspace_slug)
        transactions = _transactions(session, workspace.id)
        as_of, current = _latest_features(session, workspace.id)

    segmentation_path = artifact_dir / "segmentation.joblib"
    segmentation = train_segmentation(current, segmentation_path)
    assignments = segmentation["assignments"]
    supervised = build_supervised_snapshots(transactions)
    if training_output:
        training_output.parent.mkdir(parents=True, exist_ok=True)
        supervised.to_csv(training_output, index=False)
    supervised_artifacts = train_supervised_models(supervised, artifact_dir)

    churn_payload = load_artifact(artifact_dir / "churn.joblib")
    propensity_payload = load_artifact(artifact_dir / "propensity.joblib")
    churn_scores = score_binary_model(current, churn_payload)
    propensity_scores = score_binary_model(current, propensity_payload)

    recommender = HybridRecommender().fit(transactions, assignments)
    recommender_metrics = recommender.evaluate_leave_last_out(transactions)
    recommender_path = artifact_dir / "recommender.joblib"
    recommender.save(recommender_path, recommender_metrics)

    with session_scope(engine) as session:
        workspace = _workspace(session, workspace_slug)
        segment_run = _add_run(
            session,
            workspace_id=workspace.id,
            model_type="segmentation",
            version="segmentation-v1",
            artifact_path=segmentation_path,
            parameters={"selected_k": segmentation["metadata"]["selected_k"]},
            metrics={
                "silhouette": segmentation["metadata"]["silhouette"],
                "stability": segmentation["metadata"]["stability"],
            },
            features=SEGMENT_FEATURES,
            trained_from=None,
            trained_through=as_of,
        )
        churn_artifact = supervised_artifacts["churn"]
        churn_run = _add_run(
            session,
            workspace_id=workspace.id,
            model_type="churn",
            version=churn_artifact.version,
            artifact_path=churn_artifact.path,
            parameters={"threshold": churn_payload["threshold"], "horizon_days": 90},
            metrics=churn_artifact.metrics,
            features=churn_artifact.feature_names,
            trained_from=pd.to_datetime(supervised["snapshot_date"]).min().to_pydatetime(),
            trained_through=pd.to_datetime(supervised["snapshot_date"]).max().to_pydatetime(),
        )
        propensity_artifact = supervised_artifacts["propensity"]
        propensity_run = _add_run(
            session,
            workspace_id=workspace.id,
            model_type="propensity",
            version=propensity_artifact.version,
            artifact_path=propensity_artifact.path,
            parameters={"threshold": propensity_payload["threshold"], "horizon_days": 30},
            metrics=propensity_artifact.metrics,
            features=propensity_artifact.feature_names,
            trained_from=pd.to_datetime(supervised["snapshot_date"]).min().to_pydatetime(),
            trained_through=pd.to_datetime(supervised["snapshot_date"]).max().to_pydatetime(),
        )
        recommender_run = _add_run(
            session,
            workspace_id=workspace.id,
            model_type="recommender",
            version="recommender-v1",
            artifact_path=recommender_path,
            parameters={"method": "item-item-plus-popularity"},
            metrics=recommender_metrics,
            features=["customer_product_interactions"],
            trained_from=pd.to_datetime(transactions["invoice_date"]).min().to_pydatetime(),
            trained_through=as_of,
        )

        session.execute(
            insert(CustomerSegment),
            [
                {
                    "workspace_id": workspace.id,
                    "customer_id": int(row.customer_id),
                    "model_run_id": segment_run.id,
                    "as_of": as_of,
                    "cluster_id": int(row.cluster_id),
                    "segment_name": row.segment_name,
                    "distance_to_centroid": float(row.distance_to_centroid),
                }
                for row in assignments.itertuples()
            ],
        )
        global_explanations = {
            "churn": churn_artifact.metrics.get("global_explanations", []),
            "propensity": propensity_artifact.metrics.get("global_explanations", []),
        }
        for score_type, run, scores in (
            ("churn", churn_run, churn_scores),
            ("propensity", propensity_run, propensity_scores),
        ):
            session.execute(
                insert(ModelScore),
                [
                    {
                        "workspace_id": workspace.id,
                        "customer_id": int(row.customer_id),
                        "model_run_id": run.id,
                        "score_type": score_type,
                        "as_of": as_of,
                        "score": float(row.score),
                        "predicted_label": bool(row.predicted_label),
                        "explanation": {"top_global_drivers": global_explanations[score_type]},
                    }
                    for row in scores.itertuples()
                ],
            )
        recommendations = []
        segment_lookup = assignments.set_index("customer_id")["segment_name"].to_dict()
        for customer_id in current["customer_id"]:
            for rank, recommendation in enumerate(
                recommender.recommend(
                    int(customer_id), segment_name=segment_lookup.get(customer_id), k=5
                ),
                start=1,
            ):
                recommendations.append(
                    {
                        "workspace_id": workspace.id,
                        "customer_id": int(customer_id),
                        "product_id": recommendation.product_id,
                        "model_run_id": recommender_run.id,
                        "as_of": as_of,
                        "rank": rank,
                        "score": recommendation.score,
                        "reason": recommendation.reason,
                    }
                )
        if recommendations:
            session.execute(insert(ProductRecommendation), recommendations)

    metrics = {
        "segmentation": segmentation["metadata"],
        "churn": supervised_artifacts["churn"].metrics,
        "propensity": supervised_artifacts["propensity"].metrics,
        "recommender": recommender_metrics,
    }
    (artifact_dir / "training_summary.json").write_text(
        json.dumps(metrics, indent=2, default=str) + "\n"
    )
    return TrainingSummary(
        as_of,
        len(current),
        len(supervised),
        {
            "segmentation": str(segmentation_path),
            "churn": str(artifact_dir / "churn.joblib"),
            "propensity": str(artifact_dir / "propensity.joblib"),
            "recommender": str(recommender_path),
        },
        metrics,
    )
