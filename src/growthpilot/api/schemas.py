from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class CopilotRequest(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    conversation_id: uuid.UUID | None = None


class ActionCreate(BaseModel):
    customer_id: int
    action_type: str
    title: str
    rationale: str = ""
    priority_score: float = Field(default=0, ge=0, le=100)
    status: str = "recommended"


class ActionUpdate(BaseModel):
    status: str
    outcome: str | None = None
    outcome_value: Decimal | None = None


class ApiMessage(BaseModel):
    status: str
    data: dict[str, Any] = {}
