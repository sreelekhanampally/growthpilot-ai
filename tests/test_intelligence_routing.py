from growthpilot.services.intelligence import IntelligenceService


def test_high_risk_hyphenated_question_uses_churn_scores():
    service = object.__new__(IntelligenceService)
    service.dashboard = lambda: {
        "currency": "GBP",
        "customers": 10,
        "lifetime_revenue": 1000,
        "high_churn_risk": 2,
        "sales_opportunities": 3,
        "segments": [],
    }
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
