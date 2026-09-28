from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from growthpilot.agents.synthesis import customer_answer, knowledge_answer
from growthpilot.rag.retrieval import InMemoryRetriever


@dataclass(frozen=True)
class CopilotAnswer:
    answer: str
    intent: str
    citations: list[dict[str, Any]]
    data: dict[str, Any]


class CopilotService:
    """Route questions to analytics, customer tools, and knowledge retrieval."""

    _CUSTOMER_ID = re.compile(
        r"\bcustomer\s*(?:#|id\s*[:#]?)?\s*([a-z0-9-]*\d[a-z0-9-]*)\b",
        re.IGNORECASE,
    )
    _KNOWLEDGE_TERMS = (
        "strategy",
        "strategies",
        "playbook",
        "best practice",
        "what should we do",
        "how should we",
        "retention plan",
    )
    _OPPORTUNITY_TERMS = (
        "contact today",
        "should contact",
        "sales team contact",
        "sales opportunity",
        "sales opportunities",
        "high propensity",
        "purchase intent",
    )
    _ANALYTICS_TERMS = (
        "revenue",
        "segment",
        "how many",
        "high risk",
        "high-risk",
        "churn risk",
        "at risk customers",
        "at-risk customers",
        "top customer",
    )

    def __init__(
        self,
        *,
        analytics: Callable[[str], dict[str, Any]],
        customer_lookup: Callable[[str], dict[str, Any]],
        retriever: InMemoryRetriever,
    ):
        self.analytics = analytics
        self.customer_lookup = customer_lookup
        self.retriever = retriever

    def answer(self, question: str) -> CopilotAnswer:
        normalized = question.lower().strip()
        customer_match = self._CUSTOMER_ID.search(normalized)
        if customer_match:
            customer = self.customer_lookup(customer_match.group(1))
            answer = customer_answer(question, customer)
            return CopilotAnswer(answer, "customer_intelligence", [], customer)
        if any(term in normalized for term in self._KNOWLEDGE_TERMS):
            return self._knowledge_answer(question)
        if any(term in normalized for term in self._OPPORTUNITY_TERMS):
            return self._analytics_answer(normalized, "sales_opportunities")
        if any(term in normalized for term in self._ANALYTICS_TERMS):
            return self._analytics_answer(normalized, "analytics")
        return self._knowledge_answer(question)

    def _analytics_answer(self, question: str, intent: str) -> CopilotAnswer:
        data = self.analytics(question)
        citations = []
        if source := data.get("source"):
            citations.append({"source": source, "score": 1.0})
        return CopilotAnswer(
            data.get("summary", "The requested metric was calculated from the analytics database."),
            intent,
            citations,
            data,
        )

    def _knowledge_answer(self, question: str) -> CopilotAnswer:
        chunks = self.retriever.search(question)
        citations = [{"source": item.source, "score": item.score} for item in chunks]
        answer = knowledge_answer(question, chunks)
        return CopilotAnswer(answer, "knowledge", citations, {})
