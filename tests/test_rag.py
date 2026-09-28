import numpy as np

from growthpilot.rag.copilot import CopilotService
from growthpilot.rag.embeddings import EmbeddingModel
from growthpilot.rag.retrieval import InMemoryRetriever, chunk_text


def test_hash_embeddings_are_normalized_and_deterministic():
    model = EmbeddingModel(dimensions=64)
    model._model = None
    first = model.encode(["retain valuable customers"])
    second = model.encode(["retain valuable customers"])
    assert np.allclose(first, second)
    assert np.isclose(np.linalg.norm(first[0]), 1.0)


def test_retriever_returns_relevant_source():
    model = EmbeddingModel(dimensions=64)
    model._model = None
    retriever = InMemoryRetriever(model)
    retriever.add(
        source="retention.md",
        content="Retention offers should protect valuable customers at risk of churn.",
    )
    retriever.add(
        source="sales.md", content="Cross-sell complementary products when purchase intent is high."
    )
    result = retriever.search("How should we retain a churn risk?", k=1)
    assert result[0].source == "retention.md"


def test_chunking_uses_overlap():
    chunks = chunk_text(" ".join(str(index) for index in range(30)), words=10, overlap=2)
    assert chunks[0].split()[-2:] == chunks[1].split()[:2]


def test_copilot_routes_customer_question():
    retriever = InMemoryRetriever(EmbeddingModel(dimensions=32))
    retriever.embedding_model._model = None
    service = CopilotService(
        analytics=lambda _: {"summary": "metric"},
        customer_lookup=lambda _: {
            "external_customer_id": "42",
            "segment_name": "Champion",
            "churn_probability": 0.2,
            "propensity_probability": 0.8,
            "next_action": {"title": "Cross-sell"},
        },
        retriever=retriever,
    )
    answer = service.answer("Why contact customer 42?")
    assert answer.intent == "customer_intelligence"
    assert "Cross-sell" in answer.answer


def test_copilot_routes_plural_customers_contact_question_to_sql():
    calls: list[str] = []
    retriever = InMemoryRetriever(EmbeddingModel(dimensions=32))
    retriever.embedding_model._model = None
    service = CopilotService(
        analytics=lambda question: calls.append(question)
        or {
            "summary": "Contact customers 15000 and 15001.",
            "source": "SQL: model_scores + customers",
        },
        customer_lookup=lambda identifier: (_ for _ in ()).throw(
            AssertionError(f"customer lookup should not receive {identifier!r}")
        ),
        retriever=retriever,
    )

    answer = service.answer("Which customers should my sales team contact today?")

    assert answer.intent == "sales_opportunities"
    assert calls == ["which customers should my sales team contact today?"]
    assert answer.citations[0]["source"].startswith("SQL:")


def test_copilot_requires_a_real_customer_identifier():
    retriever = InMemoryRetriever(EmbeddingModel(dimensions=32))
    retriever.embedding_model._model = None
    retriever.add(source="playbook.md", content="Customers benefit from retention outreach.")
    service = CopilotService(
        analytics=lambda _: {"summary": "metric"},
        customer_lookup=lambda identifier: (_ for _ in ()).throw(
            AssertionError(f"unexpected customer identifier {identifier!r}")
        ),
        retriever=retriever,
    )

    answer = service.answer("What retention strategy is best for customers?")

    assert answer.intent == "knowledge"


def test_copilot_routes_high_risk_customer_list_to_sql():
    retriever = InMemoryRetriever(EmbeddingModel(dimensions=32))
    retriever.embedding_model._model = None
    service = CopilotService(
        analytics=lambda _: {"summary": "High-risk customers", "source": "SQL: model_scores"},
        customer_lookup=lambda _: {},
        retriever=retriever,
    )

    answer = service.answer("Show high-risk customers with churn risk above 70%")

    assert answer.intent == "analytics"
    assert answer.data["source"] == "SQL: model_scores"
