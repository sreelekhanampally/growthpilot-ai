from growthpilot.services.intelligence import IntelligenceService


def _dashboard() -> dict:
    return {
        "currency": "GBP",
        "customers": 240,
        "lifetime_revenue": 865_258.09,
        "high_churn_risk": 2,
        "sales_opportunities": 3,
        "segments": [],
    }


def test_high_risk_hyphenated_question_uses_churn_scores():
    service = object.__new__(IntelligenceService)
    service.dashboard = _dashboard
    service.high_risk_customers = lambda limit: [
        {
            "external_customer_id": "15000",
            "country": "United Kingdom",
            "churn_probability": 0.82,
        }
    ]

    result = service.analytics_answer(
        "What retention strategy should we use for high-risk customers?"
    )

    assert result["customers"][0]["external_customer_id"] == "15000"
    assert "Highest-risk customers" in result["summary"]
    assert "latest churn model" in result["source"]


def test_customer_count_question_does_not_fall_through_to_revenue():
    service = object.__new__(IntelligenceService)
    service.dashboard = _dashboard

    result = service.analytics_answer("How many customers do we have?")

    assert result["summary"] == "GrowthPilot currently has 240 customers."
    assert result["customer_count"] == 240
    assert result["source"] == "SQL: customers"
    assert "revenue" not in result["summary"].lower()


def test_propensity_question_uses_sales_opportunities():
    service = object.__new__(IntelligenceService)
    service.dashboard = _dashboard
    service.opportunities = lambda limit: [
        {
            "external_customer_id": "15001",
            "country": "United Kingdom",
            "propensity_probability": 0.91,
        }
    ]

    result = service.analytics_answer("Who has the highest purchase propensity?")

    assert result["customers"][0]["external_customer_id"] == "15001"
    assert "15001 (91%)" in result["summary"]
    assert "latest propensity model" in result["source"]


def test_unknown_analytics_question_does_not_claim_revenue():
    service = object.__new__(IntelligenceService)
    service.dashboard = _dashboard

    result = service.analytics_answer("How many refunds were manually approved?")

    assert "could not map" in result["summary"]
    assert "865,258.09" not in result["summary"]
