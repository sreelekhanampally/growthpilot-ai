from __future__ import annotations

import os
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from growthpilot import __version__
from growthpilot.agents import GrowthPilotAgentGraph, build_llm_service
from growthpilot.api.dependencies import get_engine
from growthpilot.api.schemas import ActionCreate, ActionUpdate, CopilotRequest
from growthpilot.config import ProjectPaths
from growthpilot.rag.retrieval import InMemoryRetriever
from growthpilot.services.intelligence import IntelligenceService

retriever = InMemoryRetriever()
llm_service = build_llm_service()


@asynccontextmanager
async def lifespan(_: FastAPI):
    configured_path = os.getenv("GROWTHPILOT_PLAYBOOK")
    playbook = Path(configured_path) if configured_path else (
        ProjectPaths().root / "docs" / "playbooks" / "retention_playbook.md"
    )
    if configured_path and not playbook.is_absolute():
        playbook = ProjectPaths().root / playbook
    if playbook.exists():
        retriever.add(source=str(playbook), content=playbook.read_text(encoding="utf-8"))
    yield


app = FastAPI(title="GrowthPilot AI API", version=__version__, lifespan=lifespan)
origins = [value.strip() for value in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def service() -> IntelligenceService:
    return IntelligenceService(get_engine(), os.getenv("WORKSPACE_SLUG", "demo-retail"))


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "version": __version__,
        "copilot": "multi_agent",
        "llm_provider": llm_service.mode,
    }


@app.get("/api/v1/dashboard/summary")
def dashboard() -> dict:
    try:
        return service().dashboard()
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.get("/api/v1/customers")
def customers(
    limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0), search: str | None = None
) -> list[dict]:
    try:
        return service().customers(limit=limit, offset=offset, search=search)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.get("/api/v1/customers/{customer_id}")
def customer(customer_id: str) -> dict:
    try:
        return service().customer_360(customer_id)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.get("/api/v1/segments")
def segments() -> list[dict]:
    return service().segments()


@app.get("/api/v1/opportunities")
def opportunities(limit: int = Query(50, ge=1, le=200)) -> list[dict]:
    return service().opportunities(limit)


@app.get("/api/v1/models/performance")
def models() -> list[dict]:
    return service().model_performance()


@app.post("/api/v1/actions")
def create_action(payload: ActionCreate) -> dict:
    return service().create_action(payload.customer_id, payload.model_dump(exclude={"customer_id"}))


@app.patch("/api/v1/actions/{action_id}")
def update_action(action_id: uuid.UUID, payload: ActionUpdate) -> dict:
    try:
        return service().update_action(action_id, **payload.model_dump())
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.post("/api/v1/copilot/chat")
async def copilot(payload: CopilotRequest) -> dict:
    intelligence = service()
    assistant = GrowthPilotAgentGraph(
        analytics=intelligence.analytics_answer,
        customer_lookup=intelligence.customer_360,
        retriever=retriever,
        llm=llm_service,
    )
    try:
        answer = await assistant.run(payload.question)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    return answer.model_dump()
