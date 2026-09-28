from growthpilot.decision.engine import choose_next_action


def test_high_value_high_risk_customer_gets_retention_action():
    action = choose_next_action(
        segment_name="High-Value At Risk",
        churn_probability=0.86,
        propensity_probability=0.58,
        monetary_value=8500,
        recommended_product_id=42,
    )
    assert action.action_type == "retention"
    assert action.recommended_product_id == 42
    assert action.priority_score > 70


def test_high_propensity_customer_gets_cross_sell():
    action = choose_next_action(
        segment_name="Loyal Customers",
        churn_probability=0.1,
        propensity_probability=0.91,
        monetary_value=1200,
    )
    assert action.action_type == "cross_sell"


def test_low_signal_customer_is_nurtured():
    action = choose_next_action(
        segment_name="Potential Loyalists",
        churn_probability=0.2,
        propensity_probability=0.3,
        monetary_value=200,
    )
    assert action.action_type == "nurture"
