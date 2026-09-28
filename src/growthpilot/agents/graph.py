from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from typing import Any

from growthpilot.agents.llm import ResilientLLMService
from growthpilot.agents.schemas import AgentCitation, AgentResponse, TraceEvent
from growthpilot.agents.state import AgentState
from growthpilot.agents.synthesis import customer_answer, knowledge_answer
from growthpilot.agents.validator import GroundingValidator
from growthpilot.rag.retrieval import InMemoryRetriever, RetrievedChunk


class GrowthPilotAgentGraph:
    """Supervisor -> specialists -> reasoning -> validator -> optional repair."""

    def __init__(
        self,
        *,
        analytics: Callable[[str], dict[str, Any]],
        customer_lookup: Callable[[str], dict[str, Any]],
        retriever: InMemoryRetriever,
        llm: ResilientLLMService,
        validator: GroundingValidator | None = None,
    ):
        self.analytics = analytics
        self.customer_lookup = customer_lookup
        self.retriever = retriever
        self.llm = llm
        self.validator = validator or GroundingValidator()

    @staticmethod
    def _trace(state: AgentState, node: str, detail: str) -> None:
        state.setdefault("trace", []).append(TraceEvent(node=node, detail=detail))

    @staticmethod
    def _chunk_citation(chunk: RetrievedChunk) -> AgentCitation:
        digest = hashlib.sha256(f"{chunk.source}:{chunk.content}".encode()).hexdigest()[:12]
        return AgentCitation(
            source=chunk.source,
            chunk_id=digest,
            excerpt=chunk.content[:280],
            score=chunk.score,
        )

    async def _run_tools(self, state: AgentState) -> str:
        decision = state["route_decision"]
        question = state["question"]
        evidence_parts: list[str] = []
        deterministic_parts: list[str] = []

        if decision.route in {"analytics", "hybrid"}:
            analytics_data = self.analytics(question.lower())
            state.setdefault("data", {})["analytics"] = analytics_data
            summary = str(analytics_data.get("summary", "Analytics completed."))
            deterministic_parts.append(summary)
            evidence_parts.append(
                "STRUCTURED ANALYTICS:\n" + json.dumps(analytics_data, default=str)
            )
            source = str(analytics_data.get("source", "GrowthPilot analytics database"))
            state.setdefault("citations", []).append(
                AgentCitation(
                    source=source,
                    chunk_id="structured-analytics",
                    excerpt=summary[:280],
                    score=1.0,
                )
            )
            self._trace(
                state,
                "analytics_agent",
                f"Called an allow-listed analytics function. Source: {source}.",
            )

        if decision.route == "customer_intelligence":
            identifier = decision.customer_identifier
            if not identifier:
                raise LookupError("A customer identifier is required for Customer 360")
            customer = self.customer_lookup(identifier)
            state.setdefault("data", {})["customer"] = customer
            summary = customer_answer(question, customer)
            deterministic_parts.append(summary)
            evidence_parts.append(
                "CUSTOMER 360 + MODEL OUTPUTS:\n" + json.dumps(customer, default=str)
            )
            state.setdefault("citations", []).append(
                AgentCitation(
                    source="Customer 360 + approved model scores",
                    chunk_id=f"customer-{identifier}",
                    excerpt=summary[:280],
                    score=1.0,
                )
            )
            self._trace(
                state,
                "customer_intelligence_agent",
                "Loaded Customer 360, model scores, recommendations, and next action "
                f"for {identifier}.",
            )

        if decision.route in {"knowledge", "hybrid"}:
            chunks = self.retriever.search(question)
            deterministic_parts.append(knowledge_answer(question, chunks))
            if chunks:
                evidence_parts.append(
                    "APPROVED PLAYBOOK CHUNKS:\n"
                    + "\n\n".join(
                        f"SOURCE: {chunk.source}\n{chunk.content}" for chunk in chunks
                    )
                )
                state.setdefault("citations", []).extend(
                    self._chunk_citation(chunk) for chunk in chunks
                )
            self._trace(
                state,
                "retrieval_agent",
                f"Retrieved {len(chunks)} semantically ranked playbook chunk(s).",
            )

        state["evidence"] = "\n\n".join(evidence_parts)
        if not deterministic_parts:
            return "I do not have enough GrowthPilot evidence to answer that reliably."
        return "\n\n".join(deterministic_parts)

    async def run(self, question: str) -> AgentResponse:
        state: AgentState = {
            "question": question,
            "trace": [],
            "citations": [],
            "data": {},
            "validation_attempts": 0,
        }
        decision, route_provider = await self.llm.route(question)
        state["route_decision"] = decision
        self._trace(
            state,
            "supervisor_agent",
            f"Route={decision.route} via {route_provider}. {decision.rationale}",
        )

        deterministic_answer = await self._run_tools(state)
        answer, answer_provider = await self.llm.answer(
            question,
            state.get("evidence", ""),
            deterministic_answer,
        )
        state["answer"] = answer
        state["provider"] = answer_provider
        self._trace(
            state,
            "reasoning_agent",
            f"Synthesized a bounded answer using {answer_provider}.",
        )

        validation = self.validator.validate(answer, state.get("evidence", ""))
        state["validation"] = validation
        self._trace(
            state,
            "validator_agent",
            f"Grounded={validation.grounded}; confidence={validation.confidence:.2f}. "
            f"{validation.notes}",
        )

        if not validation.grounded:
            repaired, repair_provider = await self.llm.repair(
                question,
                answer,
                state.get("evidence", ""),
                validation.notes,
                deterministic_answer,
            )
            state["answer"] = repaired
            state["provider"] = repair_provider
            state["validation_attempts"] = 1
            self._trace(
                state,
                "repair_agent",
                f"Removed unsupported claims using {repair_provider}.",
            )
            state["validation"] = self.validator.validate(
                repaired,
                state.get("evidence", ""),
            )
            self._trace(
                state,
                "validator_agent",
                "Revalidated the repaired answer; the graph stops after one repair pass.",
            )

        return AgentResponse(
            answer=state["answer"],
            intent=decision.route,
            route=decision.route,
            citations=state.get("citations", []),
            data=state.get("data", {}),
            trace=state.get("trace", []),
            validation=state["validation"],
            provider=state.get("provider", "deterministic"),
        )
