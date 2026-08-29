"""Live, zero-authority adapter for Alpha V4 forward-shadow observation."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from ats.intelligence.alpha_v4 import AlphaBar, AlphaOptionQuote, AlphaV4Decision, evaluate_alpha_v4
from ats.market.derivatives.option_universe import DEFAULT_MAXIMUM_QUOTE_AGE_MS
from ats.market.feeds.upstox_v3.messages import NormalizedFeedUpdate

ALPHA_V4_MODEL_VERSION = "4.1.0"
ALPHA_V4_REGIME_VERSION = "ALPHA_V4_REGIME_V1"
ALPHA_V4_ECONOMIC_MODEL_VERSION = "UNAVAILABLE_FORWARD_ECONOMICS_V1"
ALPHA_V4_FRESHNESS_POLICY_VERSION = "OPTION_UNIVERSE_2000MS_V1"
ALPHA_V4_FEATURE_SCHEMA = "1m,3m,5m,10m,15m,30m;four-clock-v1"
ALPHA_V4_CONFIG_HASH = hashlib.sha256(
    b"ALPHA_V4:4.1.0:SHADOW_ONLY:payoff-unavailable:2000ms"
).hexdigest()
ALPHA_V4_FEATURE_SCHEMA_HASH = hashlib.sha256(ALPHA_V4_FEATURE_SCHEMA.encode()).hexdigest()


@dataclass
class _MinuteAccumulator:
    minute: datetime
    event_time: datetime
    source_time: datetime
    ingest_time: datetime
    available_time: datetime
    open: float
    high: float
    low: float
    close: float

    def bar(self) -> AlphaBar:
        # Index volume is not supplied by the provider. Zero is Alpha V4's
        # explicit missing-value representation and cannot create volume edge.
        return AlphaBar(
            self.event_time,
            self.source_time,
            self.ingest_time,
            self.available_time,
            self.open,
            self.high,
            self.low,
            self.close,
            0.0,
        )


class AlphaV4ForwardShadowAdapter:
    """Collect provider-timestamped one-minute evidence without execution seams."""

    def __init__(self) -> None:
        self._minutes: dict[str, list[_MinuteAccumulator]] = {}
        self._invalid_temporal: set[str] = set()

    def ingest(self, underlying: str, update: NormalizedFeedUpdate) -> None:
        price = update.last_traded_price
        source_time = update.price_source_timestamp or update.exchange_timestamp
        if price is None or source_time is None:
            self._invalid_temporal.add(underlying)
            return
        received_at = update.received_at
        if source_time.tzinfo is None or received_at.tzinfo is None or source_time > received_at:
            self._invalid_temporal.add(underlying)
            return
        self._invalid_temporal.discard(underlying)
        minute = source_time.replace(second=0, microsecond=0)
        series = self._minutes.setdefault(underlying, [])
        value = float(price)
        if series and series[-1].minute == minute:
            current = series[-1]
            if source_time < current.event_time:
                return
            current.event_time = source_time
            current.source_time = source_time
            current.ingest_time = received_at
            current.available_time = received_at
            current.high = max(current.high, value)
            current.low = min(current.low, value)
            current.close = value
        elif not series or minute > series[-1].minute:
            series.append(
                _MinuteAccumulator(
                    minute,
                    source_time,
                    source_time,
                    received_at,
                    received_at,
                    value,
                    value,
                    value,
                    value,
                )
            )
            del series[:-31]

    def evaluate(
        self,
        *,
        underlying: str,
        decision_time: datetime,
        ce_quote: AlphaOptionQuote | None,
        pe_quote: AlphaOptionQuote | None,
        provider_lot_size: int | None,
    ) -> AlphaV4Decision:
        bars: tuple[AlphaBar, ...]
        if underlying in self._invalid_temporal:
            invalid = AlphaBar(
                decision_time,
                decision_time,
                decision_time,
                None,
                1.0,
                1.0,
                1.0,
                1.0,
                0.0,
            )
            bars = (invalid,)
        else:
            bars = tuple(item.bar() for item in self._minutes.get(underlying, ()))
        return evaluate_alpha_v4(
            bars,
            decision_time=decision_time,
            ce_quote=ce_quote,
            pe_quote=pe_quote,
            provider_lot_size=provider_lot_size,
            expected_payoff_evidence=None,
            maximum_option_quote_age_ms=DEFAULT_MAXIMUM_QUOTE_AGE_MS,
            maximum_underlying_age_ms=DEFAULT_MAXIMUM_QUOTE_AGE_MS,
        )

    @staticmethod
    def telemetry(
        decision: AlphaV4Decision,
        *,
        market_state_id: str,
        feature_bundle_id: str,
        decision_time: datetime,
    ) -> dict[str, Any]:
        ev = decision.expected_value
        return {
            "model_id": "ALPHA_V4",
            "model_version": ALPHA_V4_MODEL_VERSION,
            "config_hash": ALPHA_V4_CONFIG_HASH,
            "feature_schema_hash": ALPHA_V4_FEATURE_SCHEMA_HASH,
            "regime_version": ALPHA_V4_REGIME_VERSION,
            "economic_model_version": ALPHA_V4_ECONOMIC_MODEL_VERSION,
            "freshness_policy_version": ALPHA_V4_FRESHNESS_POLICY_VERSION,
            "market_state_id": market_state_id,
            "feature_bundle_id": feature_bundle_id,
            "decision_time": decision_time.isoformat(),
            "p_up": decision.p_up,
            "p_down": decision.p_down,
            "p_range": decision.p_range,
            "expected_move": decision.expected_move,
            "expected_volatility": decision.expected_volatility,
            "uncertainty": decision.uncertainty,
            "regime": decision.regime.value,
            "active_specialist": decision.active_specialist,
            "preferred_expression": decision.preferred_expression.value,
            "expected_option_payoff": None if ev is None else ev.expected_option_payoff,
            "net_expected_value": None if ev is None else ev.net_expected_value,
            "edge_evaluation_state": decision.edge_evaluation_state.value,
            "recommended_action": decision.recommended_action.value,
            "reason_code": decision.reason,
            "status": "SHADOW_ONLY",
            "directional_state": (
                "DIRECTIONAL_RESEARCH_ONLY"
                if decision.reason == "ECONOMIC_PAYOFF_EVIDENCE_UNAVAILABLE"
                else decision.edge_evaluation_state.value
            ),
        }


__all__ = [
    "ALPHA_V4_CONFIG_HASH",
    "ALPHA_V4_FEATURE_SCHEMA_HASH",
    "ALPHA_V4_MODEL_VERSION",
    "AlphaV4ForwardShadowAdapter",
]
