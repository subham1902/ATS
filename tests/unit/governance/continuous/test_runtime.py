"""R12 interrupt delivery remains bounded and advisory-only."""

from __future__ import annotations

import asyncio
from uuid import UUID, uuid5

from ats.contracts.governance.types import PositionRecommendation
from ats.governance.continuous import ContinuousMarketGovernor, DispatchStatus
from ats.intelligence.advisory import AdvisoryProposal

from tests.unit.intelligence.advisory.test_position_context import context, event

_NAMESPACE = UUID("7750cc0e-5b5d-572b-a807-b7fd3caee646")


class Reader:
    def __init__(self, value):  # type: ignore[no-untyped-def]
        self.value = value

    def get(self, position_id: UUID):  # type: ignore[no-untyped-def]
        if position_id == self.value.position_thesis.position_id:
            return self.value
        return None


class Provider:
    def advise(self, *, context, trigger):  # type: ignore[no-untyped-def]
        return AdvisoryProposal(
            proposal_id=uuid5(_NAMESPACE, str(trigger.event_id)),
            position_id=context.position_thesis.position_id,
            recommendation=PositionRecommendation.HOLD,
            confidence_score=0.5,
            reason_codes=("ADVISORY_ONLY",),
            evidence_refs=(trigger.event_id,),
            rationale="Typed advisory event was considered.",
            created_at=trigger.occurred_at,
        )


def test_material_event_dispatches_without_waiting_for_next_bar() -> None:
    value = context()
    governor = ContinuousMarketGovernor(context_reader=Reader(value), advisory_provider=Provider())

    asyncio.run(governor.publish(event()))
    result = asyncio.run(governor.dispatch_next())

    assert result.status is DispatchStatus.DISPATCHED
    assert result.proposal is not None
    assert result.proposal.recommendation is PositionRecommendation.HOLD
    assert governor.pending_count() == 0


def test_unbound_event_is_ignored_fail_closed() -> None:
    value = context()
    governor = ContinuousMarketGovernor(context_reader=Reader(value), advisory_provider=Provider())
    unbound = event().model_copy(update={"position_id": None})

    asyncio.run(governor.publish(unbound))
    result = asyncio.run(governor.dispatch_next())

    assert result.status is DispatchStatus.IGNORED
    assert result.reason_codes == ("POSITION_CONTEXT_REQUIRED",)


def test_missing_context_never_calls_advisory_provider() -> None:
    value = context()
    governor = ContinuousMarketGovernor(context_reader=Reader(value), advisory_provider=Provider())
    unknown = event().model_copy(update={"position_id": uuid5(_NAMESPACE, "unknown")})

    asyncio.run(governor.publish(unknown))
    result = asyncio.run(governor.dispatch_next())

    assert result.status is DispatchStatus.IGNORED
    assert result.reason_codes == ("POSITION_CONTEXT_NOT_FOUND",)
