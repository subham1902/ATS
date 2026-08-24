"""Narrow injected-provider protocol; no SDK, transport, or credential use exists here."""

from __future__ import annotations

from typing import Protocol

from .models import AdvisoryEvent, AdvisoryProposal, PositionAdvisoryContext


class PositionAdvisoryProvider(Protocol):
    """An external Harness adapter may implement this, but it cannot receive authority objects."""

    def advise(
        self,
        *,
        context: PositionAdvisoryContext,
        trigger: AdvisoryEvent,
    ) -> AdvisoryProposal: ...


__all__ = ["PositionAdvisoryProvider"]
