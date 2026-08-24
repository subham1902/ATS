"""The Harness boundary is typed, redacted, bounded, and advisory-only."""

from __future__ import annotations

from uuid import UUID, uuid5

import pytest
from ats.governance.position import evaluate_position
from ats.intelligence.advisory import (
    AdvisoryEvent,
    AdvisoryEventKind,
    PositionAdvisoryContext,
    append_advisory_event,
    create_position_context,
)

from tests.unit.governance.position.helpers import observation

_NAMESPACE = UUID("89ec7e13-9972-5d24-960f-0d94789b34af")


def context() -> PositionAdvisoryContext:
    thesis = evaluate_position(observation()).thesis
    return PositionAdvisoryContext(
        session_id=uuid5(_NAMESPACE, "session"),
        position_thesis=thesis,
        event_history=(),
        maximum_events=2,
        created_at=thesis.as_of_time,
        updated_at=thesis.as_of_time,
        provider_label="DEEPSEEK_HARNESS_ADAPTER",
    )


def event(kind: AdvisoryEventKind = AdvisoryEventKind.PRICE_SHOCK) -> AdvisoryEvent:
    thesis = evaluate_position(observation()).thesis
    return AdvisoryEvent(
        event_id=uuid5(_NAMESPACE, kind.value),
        kind=kind,
        occurred_at=thesis.as_of_time,
        position_id=thesis.position_id,
        evidence_refs=(thesis.position_thesis_id,),
        summary="Material event requires advisory reassessment.",
    )


def test_context_accepts_frozen_position_thesis_only() -> None:
    assert create_position_context(context=context()) == context()


def test_append_is_bounded_and_deterministic() -> None:
    first = append_advisory_event(context(), event=event())
    second = append_advisory_event(first, event=event(AdvisoryEventKind.IV_SHOCK))
    third = append_advisory_event(second, event=event(AdvisoryEventKind.NEWS_EVENT))

    assert len(third.event_history) == 2
    assert third.event_history == second.event_history[1:] + (third.event_history[-1],)


def test_mismatched_position_event_is_rejected() -> None:
    item = event().model_copy(update={"position_id": uuid5(_NAMESPACE, "other")})

    with pytest.raises(ValueError, match="does not match"):
        append_advisory_event(context(), event=item)


def test_context_contains_no_order_or_token_authority_fields() -> None:
    names = set(PositionAdvisoryContext.model_fields)
    assert names.isdisjoint({"autonomy_token", "nonce", "order_intent", "broker_credentials"})
