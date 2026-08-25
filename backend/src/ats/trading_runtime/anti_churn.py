"""Anti-churn guard — EV, cooldown, instrument suppression, spread, ceiling."""

from __future__ import annotations

from dataclasses import dataclass

from ats.contracts.common import UTCDateTime


@dataclass(frozen=True)
class AntiChurnConfig:
    minimum_expected_edge_r: float = 0.15
    cooldown_after_exit_bars: int = 3
    same_instrument_cooldown_minutes: int = 15
    duplicate_thesis_suppression: bool = True
    spread_max_ticks: int = 6
    campaign_trade_ceiling: int | None = None


@dataclass(frozen=True)
class ChurnFacts:
    instrument_id: str
    direction: str
    thesis_id: str | None
    expected_edge_r: float
    spread_ticks: int | None
    bars_since_exit_same_instrument: int | None
    minutes_since_exit_same_instrument: int | None
    campaign_trades_started: int
    evaluation_time: UTCDateTime


@dataclass(frozen=True)
class ChurnResult:
    allowed: bool
    reason_codes: tuple[str, ...]


def evaluate_churn(
    *,
    config: AntiChurnConfig,
    facts: ChurnFacts,
) -> ChurnResult:
    reasons: list[str] = []

    if facts.expected_edge_r < config.minimum_expected_edge_r:
        return ChurnResult(allowed=False, reason_codes=("EDGE_BELOW_THRESHOLD",))

    if facts.spread_ticks is not None and facts.spread_ticks > config.spread_max_ticks:
        return ChurnResult(allowed=False, reason_codes=("SPREAD_TOO_WIDE",))

    ceiling = config.campaign_trade_ceiling
    if ceiling is not None and facts.campaign_trades_started >= ceiling:
        return ChurnResult(allowed=False, reason_codes=("CAMPAIGN_TRADE_CEILING",))

    bars = facts.bars_since_exit_same_instrument
    if bars is not None and bars < config.cooldown_after_exit_bars:
        reasons.append("COOLDOWN_AFTER_EXIT")

    mins = facts.minutes_since_exit_same_instrument
    if mins is not None and mins < config.same_instrument_cooldown_minutes:
        if "COOLDOWN_AFTER_EXIT" not in reasons:
            reasons.append("INSTRUMENT_COOLDOWN")

    if reasons:
        return ChurnResult(allowed=False, reason_codes=tuple(reasons))

    return ChurnResult(allowed=True, reason_codes=("ANTI_CHURN_ALLOW",))
