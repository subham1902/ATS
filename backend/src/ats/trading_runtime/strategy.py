"""Simple deterministic momentum strategy for TEST_ONLY plumbing proof.

Uses a single 5-minute bar feature: close vs previous close.
bullish momentum -> CE candidate, bearish momentum -> PE candidate.
Never bypasses portfolio, anti-churn, or A04.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from ats.contracts.common import UTCDateTime

from .anti_churn import AntiChurnConfig, ChurnFacts, ChurnResult, evaluate_churn


@dataclass(frozen=True)
class StrategyConfig:
    momentum_threshold: Decimal = Decimal("0.003")
    minimum_edge_r: float = 0.2


@dataclass(frozen=True)
class BarFeatures:
    instrument_id: str
    close: Decimal
    previous_close: Decimal | None
    evaluation_time: UTCDateTime
    data_fresh: bool


@dataclass(frozen=True)
class StrategySignal:
    instrument_id: str
    direction: str
    option_type: str
    expected_edge_r: float
    thesis_id: str
    reason_codes: tuple[str, ...]
    is_actionable: bool


def evaluate_bar(
    *,
    config: StrategyConfig,
    anti_churn: AntiChurnConfig | None,
    bar: BarFeatures,
    churn_facts: ChurnFacts | None = None,
) -> StrategySignal | None:
    if not bar.data_fresh:
        return None
    if bar.previous_close is None:
        return StrategySignal(
            instrument_id=bar.instrument_id,
            direction="HOLD",
            option_type="CE",
            expected_edge_r=0.0,
            thesis_id="insufficient-history",
            reason_codes=("INSUFFICIENT_HISTORY",),
            is_actionable=False,
        )
    prev = bar.previous_close
    change = (bar.close - prev) / prev if prev != 0 else Decimal("0")
    edge_r = float(abs(change) * Decimal("10"))
    if change >= config.momentum_threshold:
        signal = StrategySignal(
            instrument_id=bar.instrument_id,
            direction="BULLISH",
            option_type="CE",
            expected_edge_r=edge_r,
            thesis_id=f"bull-{bar.instrument_id}-{bar.evaluation_time.isoformat()}",
            reason_codes=("BULLISH_MOMENTUM",),
            is_actionable=True,
        )
    elif change <= -config.momentum_threshold:
        signal = StrategySignal(
            instrument_id=bar.instrument_id,
            direction="BEARISH",
            option_type="PE",
            expected_edge_r=edge_r,
            thesis_id=f"bear-{bar.instrument_id}-{bar.evaluation_time.isoformat()}",
            reason_codes=("BEARISH_MOMENTUM",),
            is_actionable=True,
        )
    else:
        return StrategySignal(
            instrument_id=bar.instrument_id,
            direction="HOLD",
            option_type="CE",
            expected_edge_r=edge_r,
            thesis_id=f"hold-{bar.instrument_id}",
            reason_codes=("NO_MOMENTUM",),
            is_actionable=False,
        )

    if edge_r < config.minimum_edge_r:
        return StrategySignal(
            instrument_id=signal.instrument_id,
            direction=signal.direction,
            option_type=signal.option_type,
            expected_edge_r=signal.expected_edge_r,
            thesis_id=signal.thesis_id,
            reason_codes=("EDGE_BELOW_STRATEGY_MIN",),
            is_actionable=False,
        )

    if anti_churn is not None and churn_facts is not None:
        churn: ChurnResult = evaluate_churn(config=anti_churn, facts=churn_facts)
        if not churn.allowed:
            return StrategySignal(
                instrument_id=signal.instrument_id,
                direction=signal.direction,
                option_type=signal.option_type,
                expected_edge_r=signal.expected_edge_r,
                thesis_id=signal.thesis_id,
                reason_codes=churn.reason_codes,
                is_actionable=False,
            )

    return signal


__all__ = ["BarFeatures", "StrategyConfig", "StrategySignal", "evaluate_bar"]
