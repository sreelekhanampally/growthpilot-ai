from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class NextBestAction:
    action_type: str
    title: str
    rationale: str
    priority_score: float
    recommended_product_id: int | None = None

    def as_dict(self) -> dict:
        return asdict(self)


def choose_next_action(
    *,
    segment_name: str,
    churn_probability: float,
    propensity_probability: float,
    monetary_value: float,
    recommended_product_id: int | None = None,
) -> NextBestAction:
    value_factor = min(max(monetary_value, 0.0) / 5000.0, 1.0)
    product_text = f" around product {recommended_product_id}" if recommended_product_id else ""
    if churn_probability >= 0.7 and value_factor >= 0.5:
        priority = 100 * (
            0.5 * churn_probability + 0.3 * value_factor + 0.2 * propensity_probability
        )
        return NextBestAction(
            "retention",
            "Prioritize personal retention outreach",
            f"{segment_name} customer has high value and {churn_probability:.0%} churn risk; "
            f"make a tailored offer{product_text}.",
            round(priority, 1),
            recommended_product_id,
        )
    if propensity_probability >= 0.7:
        priority = 100 * (
            0.65 * propensity_probability + 0.25 * value_factor + 0.1 * (1 - churn_probability)
        )
        return NextBestAction(
            "cross_sell",
            "Send a personalized cross-sell",
            f"Purchase propensity is {propensity_probability:.0%}; recommend the "
            f"highest-ranked unseen product{product_text}.",
            round(priority, 1),
            recommended_product_id,
        )
    if churn_probability >= 0.75:
        priority = 100 * (0.75 * churn_probability + 0.25 * value_factor)
        return NextBestAction(
            "reactivation",
            "Run a low-cost reactivation",
            f"The customer is disengaging ({churn_probability:.0%} churn risk), "
            "but expected near-term conversion is limited.",
            round(priority, 1),
            recommended_product_id,
        )
    priority = 100 * (
        0.55 * propensity_probability + 0.25 * value_factor + 0.2 * (1 - churn_probability)
    )
    return NextBestAction(
        "nurture",
        "Continue lifecycle nurture",
        "No urgent risk or buying signal; keep the customer in an appropriate nurture journey.",
        round(priority, 1),
        recommended_product_id,
    )
