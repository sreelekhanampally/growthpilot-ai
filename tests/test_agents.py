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
            "For high-value customers with churn risk above 70%, use a personal retention "
            "message and a relevant loyalty benefit."
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
            "next_action": {"title": "Personalized retention offer"},
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
