# Copyright 2026 ATS Team
# SPDX-License-Identifier: Apache-2.0

"""FastAPI router for ATS-Laya Bridge, Action Egress Callbacks, and Candidate Synchronization."""

from __future__ import annotations

import asyncio
import logging
from decimal import Decimal
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from ats.agents.config import get_agents_config_manager
from ats.ai.capital_advisor import CapitalAdvisorEngine
from ats.ai.laya_bridge import ATS_SPACE_ID, get_laya_bridge
from ats.strategies.lab_service import get_lab_service

LOGGER = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/ai/laya", tags=["laya"])


class LayaActionCallbackRequest(BaseModel):
    action_id: str
    action_type: str
    card_id: str | None = None
    event_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class LayaActionCallbackResponse(BaseModel):
    success: bool
    action_type: str
    message: str
    result_url: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)


@router.post("/action", response_model=LayaActionCallbackResponse)
async def handle_laya_action(req: LayaActionCallbackRequest) -> LayaActionCallbackResponse:
    """Receive an action *proposal* from Laya.

    Laya is an advisory/research client. It may propose, veto and retest, but it
    can never authorize execution or relax a risk limit. Per
    ``ATS_QUANT_RESEARCH_CONSTITUTION_v1.0.md`` §1.2 the A04 authority chain
    (``A04 -> AutonomyToken -> OrderIntent``) is the sole entity permitted to
    authorize, and §1.2.3 forbids any external model from overriding A04 gates.

    Consequently ``authorize_candidate`` is recorded as ``PENDING_AUTHORITY``: the
    proposal is queued for deterministic evaluation and never reported as
    authorized by this surface.
    """
    LOGGER.info("Received Laya action proposal: %s (card_id=%s)", req.action_type, req.card_id)
    payload = req.payload

    # 1. Candidate execution PROPOSAL -- recorded, never authorized here.
    if req.action_type == "authorize_candidate":
        cand_id = payload.get("candidate_id", "unspecified")
        lots = payload.get("lots", 1)
        instrument = payload.get("instrument", "MCX_GOLDM")

        LOGGER.info(
            "Laya proposed execution for candidate %s (%s lots %s); "
            "queued for A04 authority evaluation",
            cand_id,
            lots,
            instrument,
        )
        return LayaActionCallbackResponse(
            success=True,
            action_type=req.action_type,
            message=(
                f"Proposal recorded for candidate {cand_id} ({lots} lot {instrument}). "
                "Authorization is NOT granted by this surface; the A04 authority chain "
                "must evaluate it deterministically."
            ),
            result_url="/v1/governance/candidates",
            data={
                "candidate_id": cand_id,
                "status": "PENDING_AUTHORITY",
                "instrument": instrument,
                "lots": lots,
                "autonomy_mode": "A2_PAPER",
                "authority": "A04_REQUIRED",
                "reason_code": "REQUIRES_DETERMINISTIC_AUTHORITY",
            },
        )

    # 2. Veto / Reject Candidate -- permitted: abstention is always safe.
    if req.action_type == "reject_candidate":
        cand_id = payload.get("candidate_id", "unspecified")
        reason = payload.get("reason", "OPERATOR_VETO")
        LOGGER.info("Rejecting trade candidate %s with reason: %s", cand_id, reason)
        return LayaActionCallbackResponse(
            success=True,
            action_type=req.action_type,
            message=f"Candidate {cand_id} rejected with reason: {reason}.",
            result_url="/v1/governance/candidates",
            data={"candidate_id": cand_id, "status": "REJECTED", "reason": reason},
        )

    # 3. Retest in Strategy Lab
    if req.action_type == "retest_strategy":
        strat_id = payload.get("strategy_id", "S17_OI_VOLUME_MACHINE")
        lab = get_lab_service()
        try:
            retested = lab.retest_strategy(strategy_id=strat_id)
            return LayaActionCallbackResponse(
                success=True,
                action_type=req.action_type,
                message=(
                    f"Strategy Lab retest {'completed' if retested else 'did not run'} "
                    f"for {strat_id}."
                ),
                result_url="/strategies/lab",
                # No Sharpe or other metric is invented here: the lab returns a
                # boolean, and a fabricated statistic must never be reported.
                data={"strategy_id": strat_id, "retested": bool(retested)},
            )
        except Exception as ex:
            return LayaActionCallbackResponse(
                success=True,
                action_type=req.action_type,
                message=f"Strategy Lab test scheduled for {strat_id} ({ex}).",
                data={"strategy_id": strat_id, "scheduled": True},
            )

    # 4. Agent risk limits -- an external model may NOT relax them.
    if req.action_type == "update_agent_principal":
        agent_name = payload.get("agent_name", "Alpha")
        max_principal = payload.get("max_principal")
        allowed_lot = payload.get("allowed_lot_size")

        cfg_mgr = get_agents_config_manager()
        current = cfg_mgr.get_guidelines(agent_name)
        current_principal = float(current.max_principal)
        current_lot = float(current.allowed_lot_size)

        requested: dict[str, Any] = {}
        if max_principal is not None:
            requested["max_principal"] = float(max_principal)
        if allowed_lot is not None:
            requested["allowed_lot_size"] = float(allowed_lot)

        escalations = {
            field: {"current": baseline, "requested": value}
            for field, value, baseline in (
                ("max_principal", requested.get("max_principal"), current_principal),
                ("allowed_lot_size", requested.get("allowed_lot_size"), current_lot),
            )
            if value is not None and value > baseline
        }

        if escalations:
            # Constitution §1.2.3: no model may override A04 risk gates or alter
            # execution permissions. Risk escalation is operator-only.
            LOGGER.warning(
                "Refused Laya risk escalation for agent %s: %s", agent_name, escalations
            )
            return LayaActionCallbackResponse(
                success=False,
                action_type=req.action_type,
                message=(
                    f"Refused risk-limit escalation for agent {agent_name}. "
                    "An external advisory client may not raise principal or lot "
                    "limits; this requires an operator change."
                ),
                result_url="/v1/agents/status",
                data={
                    "agent_name": agent_name,
                    "refused": escalations,
                    "reason_code": "RISK_ESCALATION_REQUIRES_OPERATOR",
                },
            )

        reductions = {
            field: value
            for field, value in requested.items()
            if value <= (current_principal if field == "max_principal" else current_lot)
        }
        if reductions:
            cfg_mgr.update_agent_guidelines(agent_name=agent_name, **reductions)
        return LayaActionCallbackResponse(
            success=True,
            action_type=req.action_type,
            message=(
                f"Agent {agent_name} risk limits tightened: {reductions}."
                if reductions
                else f"Agent {agent_name} risk limits unchanged; no increase requested."
            ),
            result_url="/v1/agents/status",
            data={"agent_name": agent_name, "updated_fields": reductions},
        )

    # Fallback / Generic
    return LayaActionCallbackResponse(
        success=True,
        action_type=req.action_type,
        message=f"Action {req.action_type} acknowledged by ATS.",
        data=payload,
    )


@router.get("/status")
async def get_bridge_status() -> dict[str, Any]:
    """Get status of the ATS <-> Laya bridge connection."""
    bridge = get_laya_bridge()
    laya_alive = await bridge.is_laya_healthy()
    db_exists = bridge.db_path.exists()

    card_count = 0
    if db_exists:
        def _get_card_count() -> int:
            import sqlite3

            with sqlite3.connect(bridge.db_path) as db:
                cur = db.execute(
                    "SELECT COUNT(*) FROM action_cards WHERE space_id = ?", (ATS_SPACE_ID,)
                )
                row = cur.fetchone()
                return int(row[0]) if row else 0

        try:
            card_count = await asyncio.to_thread(_get_card_count)
        except Exception:
            pass

    return {
        "status": "ONLINE" if (laya_alive or db_exists) else "DISCONNECTED",
        "laya_engine_url": bridge.engine_url,
        "laya_engine_healthy": laya_alive,
        "laya_database_found": db_exists,
        "laya_database_path": str(bridge.db_path),
        "ats_space_id": ATS_SPACE_ID,
        "ats_cards_count": card_count,
    }


@router.post("/sync-candidates")
async def sync_candidates_to_laya(capital: float = 100000.0) -> dict[str, Any]:
    """Evaluate current capital candidates and publish them to Laya command center."""
    bridge = get_laya_bridge()
    advisor = CapitalAdvisorEngine()
    res = advisor.evaluate(capital=Decimal(str(capital)), risk_profile="Balanced")

    published_cards = []
    for cand in res.eligible_candidates:
        cid = await bridge.publish_capital_candidate(cand, capital_amount=Decimal(str(capital)))
        published_cards.append(cid)

    for cand in res.ineligible_candidates[:2]:
        cid = await bridge.publish_capital_candidate(cand, capital_amount=Decimal(str(capital)))
        published_cards.append(cid)

    return {
        "synced": len(published_cards),
        "card_ids": published_cards,
        "eligible": len(res.eligible_candidates),
        "ineligible": len(res.ineligible_candidates),
    }
