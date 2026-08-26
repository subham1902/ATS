"""Deterministic strike-window selection over the canonical contract master."""

from .engine import build_strike_window
from .errors import StrikeWindowError, StrikeWindowErrorCode
from .models import (
    PairedStrike,
    StrikeLeg,
    StrikeWindowPlan,
    StrikeWindowPolicy,
    UnpairedStrikeEvidence,
)

__all__ = [
    "PairedStrike",
    "StrikeLeg",
    "StrikeWindowError",
    "StrikeWindowErrorCode",
    "StrikeWindowPlan",
    "StrikeWindowPolicy",
    "UnpairedStrikeEvidence",
    "build_strike_window",
]
