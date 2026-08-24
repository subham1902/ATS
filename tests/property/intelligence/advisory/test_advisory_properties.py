"""Bounded and fail-closed properties for advisory session facts."""

from __future__ import annotations

import pytest
from ats.intelligence.advisory import AdvisoryEvent, AdvisoryEventKind

from tests.unit.intelligence.advisory.test_position_context import event


def test_duplicate_evidence_is_rejected() -> None:
    value = event().model_copy(update={"evidence_refs": (event().evidence_refs[0],) * 2})

    with pytest.raises(ValueError, match="deduplicated"):
        AdvisoryEvent.model_validate(value.model_dump())


@pytest.mark.parametrize("kind", tuple(AdvisoryEventKind))
def test_all_registered_interrupts_remain_data_only(kind: AdvisoryEventKind) -> None:
    value = event(kind)
    assert value.kind is kind
    assert value.summary
