from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Engine, desc, func, or_, select
from sqlalchemy.orm import Session

from growthpilot.db.models import (
    Customer,
    CustomerAction,
    CustomerFeatureSnapshot,
    CustomerSegment,
    ModelRun,
    ModelScore,
    Product,
    ProductRecommendation,
    Workspace,
)
from growthpilot.decision.engine import choose_next_action


def _number(value: Any) -> float:
    return float(value or 0)


class IntelligenceService:
    def __init__(self, engine: Engine, workspace_slug: str = "demo-retail"):
        self.engine = engine
        self.workspace_slug = workspace_slug

    def _workspace(self, session: Session) -> Workspace:
        workspace = session.scalar(select(Workspace).where(Workspace.slug == self.workspace_slug))
        if workspace is None:
            raise LookupError(f"Workspace not found: {self.workspace_slug}")
        return workspace

    @staticmethod
    def _latest_run(session: Session, workspace_id: uuid.UUID, model_type: str) -> ModelRun | None:
        return session.scalar(
            select(ModelRun)
            .where(
                ModelRun.workspace_id == workspace_id,
                ModelRun.model_type == model_type,
                ModelRun.is_approved.is_(True),
            )
            .order_by(desc(ModelRun.created_at))
            .limit(1)
        )

    def dashboard(self) -> dict[str, Any]:
        with Session(self.engine) as session:
            workspace = self._workspace(session)
            customers = (
                session.scalar(
                    select(func.count(Customer.id)).where(Customer.workspace_id == workspace.id)
                )
                or 0
            )
            revenue = session.scalar(
                select(func.coalesce(func.sum(CustomerFeatureSnapshot.monetary_value), 0)).where(
                    CustomerFeatureSnapshot.workspace_id == workspace.id,
                    CustomerFeatureSnapshot.as_of
                    == select(func.max(CustomerFeatureSnapshot.as_of))
                    .where(CustomerFeatureSnapshot.workspace_id == workspace.id)
                    .scalar_subquery(),
                )
            )
            churn_run = self._latest_run(session, workspace.id, "churn")
            propensity_run = self._latest_run(session, workspace.id, "propensity")
            high_risk = (
                session.scalar(
                    select(func.count(ModelScore.id)).where(
                        ModelScore.model_run_id == churn_run.id, ModelScore.score >= 0.7
                    )
                )
                if churn_run
                else 0
            )
            opportunities = (
                session.scalar(
                    select(func.count(ModelScore.id)).where(
                        ModelScore.model_run_id == propensity_run.id, ModelScore.score >= 0.7
                    )
                )
                if propensity_run
                else 0
            )
            segments = session.execute(
                select(CustomerSegment.segment_name, func.count(CustomerSegment.id))
                .where(CustomerSegment.workspace_id == workspace.id)
                .group_by(CustomerSegment.segment_name)
            ).all()
            return {
                "currency": workspace.currency,
                "customers": int(customers),
                "lifetime_revenue": _number(revenue),
                "high_churn_risk": int(high_risk or 0),
                "sales_opportunities": int(opportunities or 0),
                "segments": [{"name": name, "customers": count} for name, count in segments],
            }

    def customers(
        self, *, limit: int = 50, offset: int = 0, search: str | None = None
    ) -> list[dict[str, Any]]:
        with Session(self.engine) as session:
            workspace = self._workspace(session)
            statement = (
                select(Customer)
                .where(Customer.workspace_id == workspace.id)
                .order_by(desc(Customer.last_purchase_at))
                .offset(offset)
                .limit(min(limit, 200))
            )
            if search:
                statement = statement.where(Customer.external_customer_id.ilike(f"%{search}%"))
            return [
                {
                    "id": row.id,
                    "external_customer_id": row.external_customer_id,
                    "country": row.country,
                    "first_purchase_at": row.first_purchase_at,
                    "last_purchase_at": row.last_purchase_at,
                }
                for row in session.scalars(statement)
            ]

    def customer_360(self, identifier: str | int) -> dict[str, Any]:
        with Session(self.engine) as session:
            workspace = self._workspace(session)
            identifier_text = str(identifier).strip()
            condition = Customer.external_customer_id == identifier_text
            if identifier_text.isdigit():
                condition = or_(
                    Customer.id == int(identifier_text),
                    Customer.external_customer_id == identifier_text,
                )
            customer = session.scalar(
                select(Customer).where(Customer.workspace_id == workspace.id, condition)
            )
            if customer is None:
                raise LookupError(f"Customer not found: {identifier}")
            feature = session.scalar(
                select(CustomerFeatureSnapshot)
                .where(CustomerFeatureSnapshot.customer_id == customer.id)
                .order_by(desc(CustomerFeatureSnapshot.as_of))
                .limit(1)
            )
            segment = session.scalar(
                select(CustomerSegment)
                .where(CustomerSegment.customer_id == customer.id)
                .order_by(desc(CustomerSegment.as_of))
                .limit(1)
            )
            scores = {
                row.score_type: row
                for row in session.scalars(
                    select(ModelScore)
                    .where(ModelScore.customer_id == customer.id)
                    .order_by(desc(ModelScore.as_of))
                )
            }
            recommendations = session.execute(
                select(ProductRecommendation, Product)
                .join(Product, Product.id == ProductRecommendation.product_id)
                .where(ProductRecommendation.customer_id == customer.id)
                .order_by(ProductRecommendation.rank)
                .limit(5)
            ).all()
            churn = scores.get("churn")
            propensity = scores.get("propensity")
            next_action = choose_next_action(
                segment_name=segment.segment_name if segment else "Unclassified",
                churn_probability=churn.score if churn else 0.0,
                propensity_probability=propensity.score if propensity else 0.0,
                monetary_value=_number(feature.monetary_value) if feature else 0.0,
                recommended_product_id=recommendations[0][0].product_id
                if recommendations
                else None,
            )
            return {
                "id": customer.id,
                "external_customer_id": customer.external_customer_id,
                "country": customer.country,
                "segment_name": segment.segment_name if segment else "Unclassified",
                "as_of": feature.as_of if feature else None,
                "features": {
                    "recency_days": feature.recency_days,
                    "frequency_orders": feature.frequency_orders,
                    "monetary_value": _number(feature.monetary_value),
                    "average_order_value": _number(feature.average_order_value),
                    "unique_products": feature.unique_products,
                    "rfm_code": feature.rfm_code,
                }
                if feature
                else {},
                "churn_probability": churn.score if churn else 0.0,
                "churn_explanation": churn.explanation if churn else {},
                "propensity_probability": propensity.score if propensity else 0.0,
                "recommendations": [
                    {
                        "product_id": recommendation.product_id,
                        "stock_code": product.stock_code,
                        "description": product.description,
                        "rank": recommendation.rank,
                        "score": recommendation.score,
                        "reason": recommendation.reason,
                    }
                    for recommendation, product in recommendations
                ],
                "next_action": next_action.as_dict(),
            }

    def opportunities(self, limit: int = 50) -> list[dict[str, Any]]:
        with Session(self.engine) as session:
            workspace = self._workspace(session)
            run = self._latest_run(session, workspace.id, "propensity")
            if run is None:
                return []
            rows = session.execute(
                select(ModelScore, Customer)
                .join(Customer, Customer.id == ModelScore.customer_id)
                .where(ModelScore.model_run_id == run.id)
                .order_by(desc(ModelScore.score))
                .limit(min(limit, 200))
            ).all()
            return [
                {
                    "customer_id": customer.id,
                    "external_customer_id": customer.external_customer_id,
                    "country": customer.country,
                    "propensity_probability": score.score,
                }
                for score, customer in rows
            ]

    def high_risk_customers(self, limit: int = 50) -> list[dict[str, Any]]:
        with Session(self.engine) as session:
            workspace = self._workspace(session)
            run = self._latest_run(session, workspace.id, "churn")
            if run is None:
                return []
            rows = session.execute(
                select(ModelScore, Customer)
                .join(Customer, Customer.id == ModelScore.customer_id)
                .where(ModelScore.model_run_id == run.id, ModelScore.score >= 0.7)
                .order_by(desc(ModelScore.score))
                .limit(min(limit, 200))
            ).all()
            return [
                {
                    "customer_id": customer.id,
                    "external_customer_id": customer.external_customer_id,
                    "country": customer.country,
                    "churn_probability": score.score,
                }
                for score, customer in rows
            ]

    def country_performance(self, limit: int = 20) -> list[dict[str, Any]]:
        """Rank countries using the latest customer feature snapshot."""
        with Session(self.engine) as session:
            workspace = self._workspace(session)
            latest_as_of = (
                select(func.max(CustomerFeatureSnapshot.as_of))
                .where(CustomerFeatureSnapshot.workspace_id == workspace.id)
                .scalar_subquery()
            )
            rows = session.execute(
                select(
                    Customer.country,
                    func.count(Customer.id),
                    func.sum(CustomerFeatureSnapshot.monetary_value),
                    func.avg(CustomerFeatureSnapshot.monetary_value),
                )
                .join(Customer, Customer.id == CustomerFeatureSnapshot.customer_id)
                .where(
                    CustomerFeatureSnapshot.workspace_id == workspace.id,
                    CustomerFeatureSnapshot.as_of == latest_as_of,
                )
                .group_by(Customer.country)
                .order_by(desc(func.sum(CustomerFeatureSnapshot.monetary_value)))
                .limit(min(limit, 100))
            ).all()
            return [
                {
                    "country": country or "Unknown",
                    "customers": int(customers),
                    "lifetime_revenue": _number(revenue),
                    "average_customer_value": _number(average_value),
                }
                for country, customers, revenue, average_value in rows
            ]

    def segments(self) -> list[dict[str, Any]]:
        with Session(self.engine) as session:
            workspace = self._workspace(session)
            rows = session.execute(
                select(
                    CustomerSegment.segment_name,
                    func.count(CustomerSegment.id),
                    func.avg(CustomerSegment.distance_to_centroid),
                )
                .where(CustomerSegment.workspace_id == workspace.id)
                .group_by(CustomerSegment.segment_name)
                .order_by(desc(func.count(CustomerSegment.id)))
            ).all()
            return [
                {
                    "name": name,
                    "customers": count,
                    "average_distance": round(float(distance or 0), 4),
                }
                for name, count, distance in rows
            ]

    def model_performance(self) -> list[dict[str, Any]]:
        with Session(self.engine) as session:
            workspace = self._workspace(session)
            runs = session.scalars(
                select(ModelRun)
                .where(ModelRun.workspace_id == workspace.id)
                .order_by(desc(ModelRun.created_at))
                .limit(20)
            )
            return [
                {
                    "id": row.id,
                    "model_type": row.model_type,
                    "version": row.version,
                    "metrics": row.metrics,
                    "trained_from": row.trained_from,
                    "trained_through": row.trained_through,
                    "is_approved": row.is_approved,
                    "created_at": row.created_at,
                }
                for row in runs
            ]

    def analytics_answer(self, question: str) -> dict[str, Any]:
        question = question.lower()
        dashboard = self.dashboard()
        if "country" in question:
            countries = self.country_performance()
            if not countries:
                return {
                    "summary": "No country-level customer data is available yet.",
                    "countries": [],
                    "source": "SQL: customer_feature_snapshots + customers",
                }
            if "most customer" in question or "largest customer" in question:
                countries.sort(key=lambda item: item["customers"], reverse=True)
                metric = "customer count"
            elif "average" in question or "value" in question:
                countries.sort(key=lambda item: item["average_customer_value"], reverse=True)
                metric = "average customer value"
            else:
                metric = "lifetime revenue"
            leader = countries[0]
            summary = (
                f"Based on {metric}, prioritize {leader['country']}. It has "
                f"{leader['customers']:,} customers, {dashboard['currency']} "
                f"{leader['lifetime_revenue']:,.2f} in lifetime revenue, and an average "
                f"customer value of {dashboard['currency']} "
                f"{leader['average_customer_value']:,.2f}."
            )
            return {
                "summary": summary,
                "ranking_metric": metric,
                "countries": countries,
                "source": "SQL: customer_feature_snapshots + customers",
            }
        if "segment" in question:
            segments = sorted(
                dashboard["segments"], key=lambda item: item["customers"], reverse=True
            )
            summary = (
                f"The largest segment is {segments[0]['name']} with "
                f"{segments[0]['customers']} customers."
                if segments
                else "No segment assignments are available yet."
            )
            return {
                "summary": summary,
                "segments": segments,
                "source": "SQL: customer_segments",
            }
        if "opportunit" in question or "contact" in question:
            rows = self.opportunities(20)
            top = ", ".join(
                f"{row['external_customer_id']} ({row['propensity_probability']:.0%})"
                for row in rows[:5]
            )
            summary = (
                f"Contact these customers first: {top}. "
                f"There are {dashboard['sales_opportunities']} high-propensity opportunities."
                if top
                else (
                    "No propensity scores are available. "
                    "Run the demo or propensity pipeline first."
                )
            )
            return {
                "summary": summary,
                "customers": rows,
                "source": "SQL: model_scores + customers (latest propensity model)",
            }
        if any(
            term in question
            for term in ("churn", "at risk", "at-risk", "high risk", "high-risk")
        ):
            rows = self.high_risk_customers(20)
            top = ", ".join(
                f"{row['external_customer_id']} ({row['churn_probability']:.0%})"
                for row in rows[:5]
            )
            summary = (
                f"Highest-risk customers: {top}. "
                f"There are {dashboard['high_churn_risk']} customers at or above 70% churn risk."
                if top
                else "No churn scores are available. Run the demo or churn pipeline first."
            )
            return {
                "summary": summary,
                "customers": rows,
                "source": "SQL: model_scores + customers (latest churn model)",
            }
        return {
            "summary": f"Lifetime purchase revenue is {dashboard['currency']} "
            f"{dashboard['lifetime_revenue']:,.2f} across "
            f"{dashboard['customers']:,} customers.",
            "source": "SQL: customer_feature_snapshots + customers",
            **dashboard,
        }

    def create_action(self, customer_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        with Session(self.engine) as session:
            workspace = self._workspace(session)
            action = CustomerAction(
                workspace_id=workspace.id,
                customer_id=customer_id,
                action_type=payload["action_type"],
                title=payload["title"],
                rationale=payload.get("rationale", ""),
                priority_score=float(payload.get("priority_score", 0)),
                status=payload.get("status", "recommended"),
            )
            session.add(action)
            session.commit()
            return {"id": action.id, "status": action.status}

    def update_action(
        self,
        action_id: uuid.UUID,
        *,
        status: str,
        outcome: str | None = None,
        outcome_value: Decimal | None = None,
    ) -> dict[str, Any]:
        with Session(self.engine) as session:
            action = session.get(CustomerAction, action_id)
            if action is None:
                raise LookupError(f"Action not found: {action_id}")
            action.status = status
            action.outcome = outcome
            action.outcome_value = outcome_value
            if status == "completed":
                action.completed_at = datetime.now().astimezone()
            session.commit()
            return {"id": action.id, "status": action.status, "outcome": action.outcome}
