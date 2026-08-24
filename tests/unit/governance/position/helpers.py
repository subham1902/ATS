"""Bound position-monitoring fixtures with an authorized candidate lineage."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from uuid import UUID, uuid5

from ats.contracts.domain.hashing import compute_payload_hash
from ats.contracts.domain.models import Position
from ats.contracts.domain.types import DataQualityState, PositionStatus
from ats.contracts.governance.types import CandidateStatus
from ats.governance.opportunity import construct_opportunity_candidate
from ats.governance.position import PositionObservation

from tests.unit.governance.opportunity.helpers import _rehash, bound_inputs

_NAMESPACE = UUID("03eea53f-4a49-533c-8b9b-e1503863fc7d")


def observation(**updates: object) -> PositionObservation:
    values = bound_inputs()
    result = construct_opportunity_candidate(**values)
    assert result.candidate is not None
    candidate = _rehash(
        result.candidate,
        status=CandidateStatus.CONSUMED,
        risk_decision_id=uuid5(_NAMESPACE, "risk"),
        advisory_id=uuid5(_NAMESPACE, "advisory"),
        autonomy_token_id=uuid5(_NAMESPACE, "token"),
    )
    now = values["evaluation_time"]
    position = Position(
        schema_version="1.0",
        position_id=uuid5(_NAMESPACE, "position"),
        portfolio_id=uuid5(_NAMESPACE, "portfolio"),
        instrument_id=candidate.instrument_id,
        net_quantity=Decimal("65"),
        average_entry_price=Decimal("101"),
        mark_price=Decimal("105"),
        realized_pnl=Decimal("0"),
        unrealized_pnl=Decimal("260"),
        cash_effect=Decimal("-6565"),
        policy_id=values["campaign"].policy_id,
        policy_version=values["campaign"].policy_version,
        opened_at=now - timedelta(minutes=2),
        updated_at=now,
        closed_at=None,
        status=PositionStatus.OPEN,
        version=1,
        last_fill_id=uuid5(_NAMESPACE, "fill"),
        payload_hash="0" * 64,
    )
    position = position.model_copy(update={"payload_hash": compute_payload_hash(position)})
    raw = {
        "position": position,
        "originating_candidate": candidate,
        "entry_thesis": values["thesis"],
        "current_thesis": values["thesis"],
        "distribution": values["distribution"],
        "campaign": values["campaign"],
        "data_cutoff": now,
        "evaluation_time": now,
        "data_quality_state": DataQualityState.GOOD,
        "maximum_favourable_excursion_r": 0.5,
        "maximum_adverse_excursion_r": -0.1,
        "initial_risk_per_unit": Decimal("21"),
        "invalidation_triggered": False,
        "risk_reduction_required": False,
        "session_exit_required": False,
    }
    raw.update(updates)
    return PositionObservation.model_validate(raw)


__all__ = ["observation"]
