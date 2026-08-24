"""Typed advisory boundary for a future injected DeepSeek Harness adapter."""

from .models import (
    AdvisoryEvent,
    AdvisoryEventKind,
    AdvisoryProposal,
    PositionAdvisoryContext,
)
from .protocols import PositionAdvisoryProvider
from .session import append_advisory_event, create_position_context

__all__ = [
    "AdvisoryEvent",
    "AdvisoryEventKind",
    "AdvisoryProposal",
    "PositionAdvisoryContext",
    "PositionAdvisoryProvider",
    "append_advisory_event",
    "create_position_context",
]
