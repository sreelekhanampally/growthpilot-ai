from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

RouteName = Literal["analytics", "customer_intelligence", "knowledge", "hybrid"]


class RouteDecision(BaseModel):
    route: RouteName
    rationale: str = Field(min_length=1, max_length=500)
    customer_identifier: str | None = None


class TraceEvent(BaseModel):
    node: str
    detail: str


class ValidationResult(BaseModel):
    grounded: bool
    confidence: float = Field(ge=0, le=1)
    notes: str
    unsupported_claims: list[str] = Field(default_factory=list)


class AgentCitation(BaseModel):
    source: str
    chunk_id: str
    excerpt: str
    score: float | None = None


class AgentResponse(BaseModel):
    answer: str
    intent: RouteName
    route: RouteName
    citations: list[AgentCitation] = Field(default_factory=list)
    data: dict[str, Any] = Field(default_factory=dict)
    trace: list[TraceEvent] = Field(default_factory=list)
    validation: ValidationResult
    provider: str
