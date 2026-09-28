import asyncio

import httpx

from growthpilot.agents.graph import GrowthPilotAgentGraph
from growthpilot.agents.llm import ModelBackend, ResilientLLMService, deterministic_route
from growthpilot.agents.validator import GroundingValidator
from growthpilot.rag.embeddings import EmbeddingModel
from growthpilot.rag.retrieval import InMemoryRetriever


def _retriever() -> InMemoryRetriever:
    model = EmbeddingModel(dimensions=32)
    model._model = None
    retriever = InMemoryRetriever(model)
    retriever.add(
        source="retention_playbook.md",
        content=(
            "Prioritize high-value customers whose churn probability is above 70%. "
            "Begin with a personal message and offer a relevant product or modest loyalty "
            "benefit. Avoid blanket discounts when purchase intent remains strong. "
            "For loyal customers with purchase propensity above 70%, use a cross-sell message "
            "centered on the highest-ranked unseen product. Limit the message to one primary "
            "recommendation and one alternative. Dormant, low-value customers should enter a "
            "low-cost automated reactivation journey. Stop after two unanswered contacts. "
            "Champions with low churn risk should receive recognition and early access rather "
            "than aggressive promotions. Every action must record an outcome. Review conversion "
            "and incremental value by action type each month."
        ),
    )
    return retriever


def _graph(*, llm: ResilientLLMService | None = None) -> GrowthPilotAgentGraph:
    return GrowthPilotAgentGraph(
        analytics=lambda _: {
            "summary": "There are 8 customers at or above 70% churn risk.",
            "customers": [{"external_customer_id": "15000", "churn_probability": 0.82}],
            "source": "SQL: model_scores + customers",
        },
        customer_lookup=lambda identifier: {
            "external_customer_id": identifier,
            "segment_name": "High Value At Risk",
            "churn_probability": 0.82,
            "propensity_probability": 0.64,
            "features": {
                "recency_days": 79,
                "frequency_orders": 8,
                "average_order_value": 120.0,
            },
            "churn_explanation": {
                "top_global_drivers": [
                    {"feature": "orders_90d", "importance": 0.24},
                    {"feature": "recency_days", "importance": 0.10},
                ]
            },
            "recommendations": [
                {
                    "product_id": 9,
                    "stock_code": "P-009",
                    "description": "Desk organiser",
                    "rank": 1,
                    "score": 0.91,
                    "reason": "Similar customers also purchased this product",
                },
                {
                    "product_id": 10,
                    "stock_code": "P-010",
                    "description": "Storage basket",
                    "rank": 2,
                    "score": 0.85,
                    "reason": "Popular with customers like this one",
                },
            ],
            "next_action": {
                "title": "Personalized retention offer",
                "rationale": "High value and 82% churn risk justify personal outreach.",
                "priority_score": 88.0,
                "recommended_product_id": 9,
            },
        },
        retriever=_retriever(),
        llm=llm or ResilientLLMService(backends=[]),
    )


def test_agent_graph_routes_analytics_through_safe_tool():
    response = asyncio.run(_graph().run("Which customers have high churn risk?"))

    assert response.route == "analytics"
    assert response.validation.grounded is True
    assert response.provider == "deterministic"
    assert [event.node for event in response.trace] == [
        "supervisor_agent",
        "analytics_agent",
        "reasoning_agent",
        "validator_agent",
    ]
    assert response.citations[0].source.startswith("SQL:")


def test_customer_count_variants_route_to_analytics():
    for question in (
        "How many customers do we have?",
        "What is the customer count?",
        "What is the total number of customers?",
    ):
        decision = deterministic_route(question)
        assert decision is not None
        assert decision.route == "analytics"


def test_agent_graph_combines_sql_and_rag_for_strategy_question():
    response = asyncio.run(
        _graph().run("What retention strategy should we use for high-risk customers?")
    )

    assert response.route == "hybrid"
    assert response.validation.grounded is True
    assert {event.node for event in response.trace} >= {
        "supervisor_agent",
        "analytics_agent",
        "retrieval_agent",
        "reasoning_agent",
        "validator_agent",
    }
    assert len(response.citations) >= 2


def test_agent_graph_uses_customer_360_for_explicit_identifier():
    response = asyncio.run(_graph().run("Why is Customer 15000 at risk?"))

    assert response.route == "customer_intelligence"
    assert response.data["customer"]["external_customer_id"] == "15000"
    assert "Personalized retention offer" in response.answer


def test_product_question_returns_ranked_products_instead_of_generic_customer_summary():
    response = asyncio.run(_graph().run("Recommend products for Customer 15000."))

    assert response.route == "customer_intelligence"
    assert "Desk organiser (P-009)" in response.answer
    assert "Storage basket (P-010)" in response.answer
    assert "High Value At Risk segment" not in response.answer
    assert response.validation.grounded is True


def test_next_action_question_leads_with_action_and_rationale():
    response = asyncio.run(
        _graph().run("What should the sales team do next for Customer 15000?")
    )

    assert response.answer.startswith("Next action for Customer 15000")
    assert "Personalized retention offer" in response.answer
    assert "High value and 82% churn risk" in response.answer
    assert "Desk organiser (P-009)" in response.answer
    assert response.validation.grounded is True


def test_customer_risk_question_uses_profile_signals_and_model_drivers():
    response = asyncio.run(_graph().run("Why is Customer 15000 at risk?"))

    assert "82% predicted churn risk" in response.answer
    assert "79 days since the last purchase" in response.answer
    assert "orders 90d" in response.answer
    assert response.validation.grounded is True


def test_loyal_customer_question_returns_only_relevant_playbook_rules():
    response = asyncio.run(_graph().run("How should we approach loyal customers?"))

    assert "loyal customers" in response.answer
    assert "cross-sell" in response.answer
    assert "Dormant, low-value" not in response.answer
    assert len(response.answer) < 550
    assert response.validation.grounded is True


def test_best_practices_are_summarized_instead_of_dumping_the_playbook():
    response = asyncio.run(
        _graph().run("What are the best practices in our retention playbook?")
    )

    assert "Prioritize high-value" in response.answer
    assert "loyal customers" in response.answer
    assert "Dormant, low-value" in response.answer
    assert "record an outcome" in response.answer
    assert len(response.answer) < 750
    assert response.validation.grounded is True


def test_avoid_offer_question_returns_the_specific_prohibition():
    response = asyncio.run(_graph().run("What retention offer should we avoid?"))

    assert "Avoid blanket discounts" in response.answer
    assert "aggressive promotions" in response.answer
    assert "Dormant, low-value" not in response.answer
    assert response.validation.grounded is True


def test_reactivation_question_returns_reactivation_rules_only():
    response = asyncio.run(_graph().run("Give me a general customer reactivation strategy."))

    assert "low-cost automated reactivation journey" in response.answer
    assert "two unanswered contacts" in response.answer
    assert "loyal customers" not in response.answer
    assert response.validation.grounded is True


def test_hybrid_high_risk_strategy_combines_sql_with_focused_guidance():
    response = asyncio.run(
        _graph().run("What retention strategy should we use for high-risk customers?")
    )

    assert response.route == "hybrid"
    assert "There are 8 customers" in response.answer
    assert "Prioritize high-value customers" in response.answer
    assert "Dormant, low-value" not in response.answer
    assert len(response.answer) < 750
    assert response.validation.grounded is True


class ModelPlanner(ModelBackend):
    name = "test-model"

    async def complete(self, system: str, user: str, *, json_mode: bool = False) -> str:
        if json_mode:
            return (
                '{"route":"knowledge","rationale":"Qualitative guidance",'
                '"customer_identifier":null}'
            )
        return "Use a personal retention message and a relevant loyalty benefit."


def test_ambiguous_question_uses_model_supervisor_and_synthesis():
    response = asyncio.run(
        _graph(llm=ResilientLLMService(backends=[ModelPlanner()])).run(
            "Help me improve customer relationships"
        )
    )

    assert response.route == "knowledge"
    assert response.provider == "test-model"
    assert "test-model" in response.trace[0].detail
    assert response.validation.grounded is True


class RateLimitedBackend(ModelBackend):
    name = "gemini"

    async def complete(self, system: str, user: str, *, json_mode: bool = False) -> str:
        request = httpx.Request("POST", "https://example.invalid")
        response = httpx.Response(429, request=request)
        raise httpx.HTTPStatusError("429 quota exceeded", request=request, response=response)


class LocalBackend(ModelPlanner):
    name = "ollama"


def test_model_generation_fails_over_after_rate_limit():
    llm = ResilientLLMService(backends=[RateLimitedBackend(), LocalBackend()])
    response = asyncio.run(_graph(llm=llm).run("Help me improve customer relationships"))

    assert response.provider == "ollama"
    assert response.validation.grounded is True


def test_validator_rejects_unsupported_numeric_claim():
    result = GroundingValidator().validate(
        "There are 30 high-risk customers.",
        "The SQL query returned 8 high-risk customers.",
    )

    assert result.grounded is False
    assert result.unsupported_claims
