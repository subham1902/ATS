"""SAFE / NORMAL / AGGRESSIVE parameterized envelopes with auto-de-escalation only.

Hard global limits dominate. Modes affect bounded parameters only.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from ats.contracts.common import UTCDateTime


class TradingMode(StrEnum):
    SAFE = "SAFE"
    NORMAL = "NORMAL"
    AGGRESSIVE = "AGGRESSIVE"
    HALTED = "HALTED"


_MODE_ORDER: dict[TradingMode, int] = {
    TradingMode.SAFE: 0,
    TradingMode.NORMAL: 1,
    TradingMode.AGGRESSIVE: 2,
    TradingMode.HALTED: -1,
}


@dataclass(frozen=True)
class ModeEnvelope:
    mode: TradingMode
    capital_utilization: Decimal
    max_concurrent_positions: int
    minimum_expected_edge_r: float
    spread_tolerance_ticks: int
    cooldown_after_exit_minutes: int
    profit_protection_tightness: Decimal
    label: str

    def __post_init__(self) -> None:
        if self.capital_utilization <= 0 or self.capital_utilization > 1:
            raise ValueError("capital_utilization must be (0, 1]")
        if self.max_concurrent_positions <= 0:
            raise ValueError("max_concurrent_positions must be positive")


@dataclass(frozen=True)
class ModeState:
    user_selected: TradingMode
    effective: TradingMode
    deescalation_reason: str | None
    escalated_at: UTCDateTime | None


def resolve_effective_mode(
    *,
    user_selected: TradingMode,
    hwm_deescalated: TradingMode | None = None,
    safety_halted: bool = False,
    previous_effective: TradingMode | None = None,
) -> ModeState:
    if safety_halted:
        return ModeState(
            user_selected=user_selected,
            effective=TradingMode.HALTED,
            deescalation_reason="SAFETY_HALTED",
            escalated_at=None,
        )
    hwm_mode = hwm_deescalated
    if hwm_mode is not None and _MODE_ORDER[hwm_mode] < _MODE_ORDER[user_selected]:
        return ModeState(
            user_selected=user_selected,
            effective=hwm_mode,
            deescalation_reason="HWM_DRAWDOWN_DEESCALATION",
            escalated_at=None,
        )
    if previous_effective is not None:
        if _MODE_ORDER[user_selected] > _MODE_ORDER[previous_effective]:
            return ModeState(
                user_selected=user_selected,
                effective=previous_effective,
                deescalation_reason="AUTO_ESCALATION_FORBIDDEN",
                escalated_at=None,
            )
    return ModeState(
        user_selected=user_selected,
        effective=user_selected,
        deescalation_reason=None,
        escalated_at=None,
    )


def effective_envelope(
    *,
    config: dict[TradingMode, ModeEnvelope],
    effective: TradingMode,
) -> ModeEnvelope:
    return config[effective]


def is_entry_blocked_by_mode(*, envelope: ModeEnvelope, open_positions: int) -> bool:
    return open_positions >= envelope.max_concurrent_positions


__all__ = [
    "ModeEnvelope",
    "ModeState",
    "TradingMode",
    "effective_envelope",
    "is_entry_blocked_by_mode",
    "resolve_effective_mode",
]
