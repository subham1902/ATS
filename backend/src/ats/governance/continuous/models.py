"""Typed results for a read/event coordination runtime with no execution authority."""

from __future__ import annotations

from enum import StrEnum

from ats.contracts.common import ATSBaseModel
from ats.intelligence.advisory import AdvisoryEvent, AdvisoryProposal


class DispatchStatus(StrEnum):
    DISPATCHED = "DISPATCHED"
    IGNORED = "IGNORED"


class MarketEventDispatch(ATSBaseModel):
    status: DispatchStatus
    event: AdvisoryEvent
    proposal: AdvisoryProposal | None
    reason_codes: tuple[str, ...]


__all__ = ["DispatchStatus", "MarketEventDispatch"]
