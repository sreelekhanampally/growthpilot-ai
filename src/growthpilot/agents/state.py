from __future__ import annotations

from typing import Any, TypedDict

from growthpilot.agents.schemas import (
    AgentCitation,
    RouteDecision,
    TraceEvent,
    ValidationResult,
)


class AgentState(TypedDict, total=False):
    question: str
    route_decision: RouteDecision
    answer: str
    evidence: str
    citations: list[AgentCitation]
    data: dict[str, Any]
    trace: list[TraceEvent]
    validation: ValidationResult
    validation_attempts: int
    provider: str
