"""FastAPI router for managed research agents (proposal-only).

Separate from the strategy-persona playground routes in :mod:`ats.agents.router`:
those agents carry principals and trade, these agents only ever inspect,
analyze, and propose. Nothing here can construct an order, mint a token, touch
a broker, or mutate portfolio capital — the domain module has no such imports,
and the contract test ``test_managed_agent_boundary.py`` pins that.

Lifecycle audit flows through the unified activity log via an injected
announcer, so the open 24-entry domain event registry is untouched.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ats.agents.managed import (
    AGENT_STATUSES,
    AGENT_TYPES,
    CAPABILITY_ALLOWLIST,
    DATA_SCOPE_ALLOWLIST,
    RESEARCH_SCOPE_ALLOWLIST,
    ManagedAgentConflict,
    ManagedAgentError,
    ManagedAgentStore,
)

router = APIRouter(prefix="/v1/agents/managed", tags=["managed-agents"])


_STORE: ManagedAgentStore | None = None


def get_managed_store() -> ManagedAgentStore:
    """Process-wide store, wired to the activity log for lifecycle audit."""

    global _STORE
    if _STORE is None:
        _STORE = ManagedAgentStore(path=None, announce=_announce)
    return _STORE


def set_managed_store(store: ManagedAgentStore) -> ManagedAgentStore:
    global _STORE
    _STORE = store
    return store


def reset_managed_store(*, path: Path | str | None = None) -> ManagedAgentStore:
    """Drop the cached store (tests point it at a tmp file)."""
    global _STORE
    _STORE = ManagedAgentStore(
        path=Path(path) if path is not None else None, announce=_announce
    )
    return _STORE


def _announce(kind: str, summary: str) -> None:
    try:
        from ats.trading_runtime.paper_tournament import record_system_activity

        record_system_activity(event_kind=kind, summary=summary)
    except Exception:
        pass  # Audit must never break the mutation it records.


def _not_found(exc: ManagedAgentError) -> HTTPException:
    message = str(exc)
    if isinstance(exc, ManagedAgentConflict):
        return HTTPException(status_code=409, detail=message)
    if message.startswith("Unknown agent '") or message.startswith("Unknown run '"):
        return HTTPException(status_code=404, detail=message)
    if "already taken" in message or "already exists" in message:
        return HTTPException(status_code=409, detail=message)
    return HTTPException(status_code=422, detail=message)


class CreateManagedAgentRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    description: str = Field("", max_length=2000)
    agent_type: str = Field("RESEARCH", description=f"One of {list(AGENT_TYPES)}")
    provider: str = Field("", max_length=128)
    model: str = Field("", max_length=128)
    system_instructions: str = Field("", max_length=8000)
    capabilities: list[str] = Field(default_factory=list)
    data_scopes: list[str] = Field(default_factory=list)
    research_scopes: list[str] = Field(default_factory=list)
    timeout_s: float = Field(300.0, gt=0, le=86400)
    max_concurrency: int = Field(1, ge=1, le=32)
    credential_ref: str | None = Field(
        None, description="Environment variable NAME holding the credential; never a value"
    )


class UpdateManagedAgentRequest(BaseModel):
    expected_version: int | None = Field(
        None, ge=1, description="Config version the caller read; stale -> 409"
    )
    name: str | None = Field(None, min_length=1, max_length=64)
    description: str | None = Field(None, max_length=2000)
    agent_type: str | None = None
    provider: str | None = Field(None, max_length=128)
    model: str | None = Field(None, max_length=128)
    system_instructions: str | None = Field(None, max_length=8000)
    capabilities: list[str] | None = None
    data_scopes: list[str] | None = None
    research_scopes: list[str] | None = None
    timeout_s: float | None = Field(None, gt=0, le=86400)
    max_concurrency: int | None = Field(None, ge=1, le=32)
    credential_ref: str | None = None


class DuplicateManagedAgentRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)


class FinishRunRequest(BaseModel):
    ok: bool = True
    error: str | None = Field(None, max_length=2000)


@router.get("")
def list_managed_agents(
    include_archived: bool = Query(False),
) -> dict[str, Any]:
    store = get_managed_store()
    return {
        "agents": [a.as_dict() for a in store.list_agents(include_archived=include_archived)],
    }


@router.post("", status_code=201)
def create_managed_agent(body: CreateManagedAgentRequest) -> dict[str, Any]:
    store = get_managed_store()
    try:
        agent = store.create(**body.model_dump())
    except ManagedAgentError as exc:
        raise _not_found(exc) from exc
    return {"agent": agent.as_dict()}


@router.get("/schema")
def managed_agent_schema() -> dict[str, Any]:
    """Canonical closed vocabularies, so clients never keep a second copy.

    Declared before ``/{agent_id}`` so the literal path wins the match.
    """
    return {
        "agent_types": list(AGENT_TYPES),
        "statuses": list(AGENT_STATUSES),
        "capabilities": sorted(CAPABILITY_ALLOWLIST),
        "data_scopes": sorted(DATA_SCOPE_ALLOWLIST),
        "research_scopes": sorted(RESEARCH_SCOPE_ALLOWLIST),
        "limits": {
            "timeout_s": {"min_exclusive": 0, "max": 86400},
            "max_concurrency": {"min": 1, "max": 32},
        },
    }


@router.get("/{agent_id}")
def get_managed_agent(agent_id: str) -> dict[str, Any]:
    store = get_managed_store()
    try:
        agent = store.require(agent_id)
    except ManagedAgentError as exc:
        raise _not_found(exc) from exc
    return {"agent": agent.as_dict()}


@router.patch("/{agent_id}")
def update_managed_agent(agent_id: str, body: UpdateManagedAgentRequest) -> dict[str, Any]:
    store = get_managed_store()
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    expected = fields.pop("expected_version", None)
    try:
        agent = store.update(agent_id, expected_version=expected, **fields)
    except ManagedAgentError as exc:
        raise _not_found(exc) from exc
    return {"agent": agent.as_dict()}


@router.post("/{agent_id}/enable")
def enable_managed_agent(agent_id: str) -> dict[str, Any]:
    store = get_managed_store()
    try:
        agent = store.set_enabled(agent_id, True)
    except ManagedAgentError as exc:
        raise _not_found(exc) from exc
    return {"agent": agent.as_dict()}


@router.post("/{agent_id}/disable")
def disable_managed_agent(agent_id: str) -> dict[str, Any]:
    store = get_managed_store()
    try:
        agent = store.set_enabled(agent_id, False)
    except ManagedAgentError as exc:
        raise _not_found(exc) from exc
    return {"agent": agent.as_dict()}


@router.post("/{agent_id}/duplicate", status_code=201)
def duplicate_managed_agent(agent_id: str, body: DuplicateManagedAgentRequest) -> dict[str, Any]:
    store = get_managed_store()
    try:
        agent = store.duplicate(agent_id, name=body.name)
    except ManagedAgentError as exc:
        raise _not_found(exc) from exc
    return {"agent": agent.as_dict()}


@router.delete("/{agent_id}")
def delete_managed_agent(
    agent_id: str,
    hard: bool = Query(False, description="Hard-delete instead of archive"),
    confirm: bool = Query(False, description="Explicit destructive confirmation"),
) -> dict[str, Any]:
    """Archive by default. Hard deletion requires hard=true AND confirm=true
    and is refused server-side unless the agent never ran and has no history."""
    store = get_managed_store()
    try:
        if hard:
            name = store.hard_delete(agent_id, confirm=confirm)
            return {"deleted": name, "mode": "hard"}
        agent = store.archive(agent_id)
    except ManagedAgentError as exc:
        raise _not_found(exc) from exc
    return {"agent": agent.as_dict(), "mode": "archived"}


@router.get("/{agent_id}/versions")
def list_managed_agent_versions(agent_id: str) -> dict[str, Any]:
    store = get_managed_store()
    try:
        versions = store.versions(agent_id)
    except ManagedAgentError as exc:
        raise _not_found(exc) from exc
    return {"versions": [v.as_dict() for v in versions]}


@router.get("/{agent_id}/runs")
def list_managed_agent_runs(
    agent_id: str, limit: int = Query(50, ge=1, le=200)
) -> dict[str, Any]:
    store = get_managed_store()
    try:
        runs = store.runs(agent_id, limit=limit)
    except ManagedAgentError as exc:
        raise _not_found(exc) from exc
    return {"runs": [r.as_dict() for r in runs]}


@router.post("/{agent_id}/runs", status_code=201)
def start_managed_agent_run(agent_id: str) -> dict[str, Any]:
    """Record a run start. Disabled or archived agents cannot start new work;
    in-flight runs are never disturbed. This records — it does not execute."""
    store = get_managed_store()
    try:
        run = store.record_run_start(agent_id)
    except ManagedAgentError as exc:
        raise _not_found(exc) from exc
    return {"run": run.as_dict()}


@router.post("/runs/{run_id}/finish")
def finish_managed_agent_run(run_id: str, body: FinishRunRequest) -> dict[str, Any]:
    store = get_managed_store()
    try:
        run = store.record_run_finish(run_id, ok=body.ok, error=body.error)
    except ManagedAgentError as exc:
        raise _not_found(exc) from exc
    return {"run": run.as_dict()}
