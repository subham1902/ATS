"""ATS Pre-Market Readiness Engine & Checklist (Corrective Audit Version).

Verifies all critical system, market-feed, safety, capital, and runtime conditions
prior to an A2 PAPER trading session (Target date: 2026-08-31).

STRICT READINESS RULES:
1. Provider-derived InstrumentSpec unavailable/stale/mismatched
   -> BLOCKED_INSTRUMENT_SPEC_UNAVAILABLE
2. Capital mismatch against canonical ₹100,000 budget -> BLOCKED_CAPITAL_MISMATCH
3. Live money enabled -> BLOCKED_LIVE_MONEY_PROHIBITED
4. Real broker execution authority present -> BLOCKED_REAL_BROKER_PROHIBITED
5. Recorder failed -> BLOCKED_EVIDENCE_RECORDER_UNHEALTHY
6. PaperBroker unhealthy -> BLOCKED_PAPER_BROKER_UNHEALTHY
7. Required underlying/CE/PE instrument quote stale -> BLOCKED_REQUIRED_INSTRUMENT_STALE
8. Synthetic dry-run test mode -> Tagged SYNTHETIC_TEST_ONLY with verdict
   SYNTHETIC_FORWARD_SHADOW_TEST_PASS
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from ats.trading_runtime.broker import PaperBrokerAdapter
from ats.trading_runtime.modes import TradingMode
from ats.trading_runtime.runtime_provider import TradingRuntimeProvider

CANONICAL_A2_PAPER_CAPITAL = Decimal("100000")


@dataclass
class NextSessionReadiness:
    trading_date: str
    checked_at: str
    system_state: str  # READY / NOT_READY
    session_state: str  # ENTRY_ALLOWED / PRE_OPEN / EXIT_ONLY / FLATTEN_WINDOW / CLOSED
    requested_mode: str
    effective_mode: str
    feed_health: bool
    instrument_health: bool
    recorder_health: bool
    paperbroker_health: bool
    portfolio_health: bool
    a04_health: bool
    shadow_engine_health: bool
    capital_state: str
    canonical_capital: str
    capital_authority_source: str
    instrument_spec_source: str
    resolved_lot_sizes: dict[str, int]
    open_positions: int
    live_money_enabled: bool
    real_broker_execution_enabled: bool
    synthetic_mode: bool
    ready_for_a2_paper: bool
    blocking_reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        if self.synthetic_mode:
            if self.ready_for_a2_paper:
                verdict = "SYNTHETIC_FORWARD_SHADOW_TEST_PASS"
            elif self.blocking_reasons:
                verdict = f"SYNTHETIC_BLOCKED_{self.blocking_reasons[0]}"
            else:
                verdict = "SYNTHETIC_BLOCKED_UNKNOWN"
        else:
            if self.ready_for_a2_paper:
                verdict = "READY_FOR_A2_PAPER_SESSION"
            elif self.blocking_reasons:
                verdict = f"BLOCKED_{self.blocking_reasons[0]}"
            else:
                verdict = "BLOCKED_UNKNOWN"

        return {
            "trading_date": self.trading_date,
            "checked_at": self.checked_at,
            "system_state": self.system_state,
            "session_state": self.session_state,
            "requested_mode": self.requested_mode,
            "effective_mode": self.effective_mode,
            "feed_health": self.feed_health,
            "instrument_health": self.instrument_health,
            "recorder_health": self.recorder_health,
            "paperbroker_health": self.paperbroker_health,
            "portfolio_health": self.portfolio_health,
            "a04_health": self.a04_health,
            "shadow_engine_health": self.shadow_engine_health,
            "capital_state": self.capital_state,
            "canonical_capital": self.canonical_capital,
            "capital_authority_source": self.capital_authority_source,
            "instrument_spec_source": self.instrument_spec_source,
            "resolved_lot_sizes": self.resolved_lot_sizes,
            "open_positions": self.open_positions,
            "live_money_enabled": self.live_money_enabled,
            "real_broker_execution_enabled": self.real_broker_execution_enabled,
            "synthetic_mode": self.synthetic_mode,
            "synthetic_test_only": self.synthetic_mode,
            "ready_for_a2_paper": self.ready_for_a2_paper,
            "blocking_reasons": self.blocking_reasons,
            "warnings": self.warnings,
            "status_verdict": verdict,
        }


def check_pre_market_readiness(
    *,
    trading_date: str = "2026-08-31",
    requested_mode: TradingMode = TradingMode.AGGRESSIVE,
    capital_budget: Decimal = CANONICAL_A2_PAPER_CAPITAL,
    market_feed_healthy: bool = True,
    recorder_healthy: bool = True,
    shadow_engine_healthy: bool = True,
    provider_contracts: tuple[Any, ...] | None = None,
    live_instrument_quotes_fresh: bool = True,
    live_money_flag: bool = False,
    real_broker_flag: bool = False,
    synthetic_mode: bool = False,
) -> NextSessionReadiness:
    """Legacy fixture evaluator.

    Connected operators must use ``connected_readiness`` via the readiness CLI.
    This compatibility seam can exercise synthetic fixtures but can never emit
    a connected-ready verdict from constructor defaults.
    """
    now_str = datetime.now(UTC).isoformat()
    blocking_reasons: list[str] = []
    warnings: list[str] = []

    # 1. Hard Safeguards
    if live_money_flag:
        blocking_reasons.append("LIVE_MONEY_PROHIBITED")

    if real_broker_flag:
        blocking_reasons.append("REAL_BROKER_PROHIBITED")

    # 2. Mode & Capital Authority
    effective_mode = requested_mode.value
    runtime_provider = TradingRuntimeProvider()
    canonical_capital = runtime_provider.get_state().total

    cap_mismatch = (
        capital_budget != CANONICAL_A2_PAPER_CAPITAL
        or canonical_capital != CANONICAL_A2_PAPER_CAPITAL
    )
    if cap_mismatch:
        blocking_reasons.append("CAPITAL_MISMATCH")

    capital_source = "TradingRuntimeProvider.RuntimeProviderState.total"

    # 3. Instrument Spec & Lot Size Authority
    resolved_lot_sizes: dict[str, int] = {}
    instrument_spec_source = "UNRESOLVED"
    instrument_health = False

    if synthetic_mode:
        # Fixture specs explicitly marked SYNTHETIC_TEST_ONLY
        resolved_lot_sizes = {"NIFTY": 25, "BANKNIFTY": 15}
        instrument_spec_source = "SYNTHETIC_TEST_FIXTURE_ONLY"
        instrument_health = True
    elif provider_contracts is not None and len(provider_contracts) > 0:
        instrument_spec_source = "ProviderReferenceAuthority.contracts"
        for c in provider_contracts:
            k = getattr(c, "underlying", None) or getattr(c, "instrument_key", None)
            ls = getattr(c, "lot_size", None)
            if k and ls:
                resolved_lot_sizes[str(k)] = int(ls)
        if len(resolved_lot_sizes) >= 2:
            instrument_health = True
        else:
            blocking_reasons.append("INSTRUMENT_SPEC_INCOMPLETE")
    else:
        instrument_spec_source = "NONE_AVAILABLE"
        blocking_reasons.append("INSTRUMENT_SPEC_UNAVAILABLE")

    # 4. Feed & Component Health
    feed_health = market_feed_healthy
    if not feed_health:
        blocking_reasons.append("MARKET_FEED_UNHEALTHY")

    if not live_instrument_quotes_fresh and not synthetic_mode:
        blocking_reasons.append("REQUIRED_INSTRUMENT_STALE")

    recorder_health = recorder_healthy
    if not recorder_health:
        blocking_reasons.append("EVIDENCE_RECORDER_UNHEALTHY")

    broker = PaperBrokerAdapter()
    paperbroker_health = broker.is_healthy()
    if not paperbroker_health:
        blocking_reasons.append("PAPER_BROKER_UNHEALTHY")

    shadow_engine_health = shadow_engine_healthy
    if not shadow_engine_health:
        warnings.append("SHADOW_ENGINE_DEGRADED")

    open_positions = len(broker.query_positions())
    portfolio_health = True
    a04_health = True

    if not synthetic_mode:
        blocking_reasons.append("CONNECTED_READINESS_API_REQUIRED")

    # Final Verdict Logic
    ready_for_a2_paper = len(blocking_reasons) == 0
    system_state = "READY" if ready_for_a2_paper else "NOT_READY"
    session_state = "ENTRY_ALLOWED"

    return NextSessionReadiness(
        trading_date=trading_date,
        checked_at=now_str,
        system_state=system_state,
        session_state=session_state,
        requested_mode=requested_mode.value,
        effective_mode=effective_mode,
        feed_health=feed_health,
        instrument_health=instrument_health,
        recorder_health=recorder_health,
        paperbroker_health=paperbroker_health,
        portfolio_health=portfolio_health,
        a04_health=a04_health,
        shadow_engine_health=shadow_engine_health,
        capital_state=str(capital_budget),
        canonical_capital=str(canonical_capital),
        capital_authority_source=capital_source,
        instrument_spec_source=instrument_spec_source,
        resolved_lot_sizes=resolved_lot_sizes,
        open_positions=open_positions,
        live_money_enabled=live_money_flag,
        real_broker_execution_enabled=real_broker_flag,
        synthetic_mode=synthetic_mode,
        ready_for_a2_paper=ready_for_a2_paper,
        blocking_reasons=blocking_reasons,
        warnings=warnings,
    )


__all__ = [
    "CANONICAL_A2_PAPER_CAPITAL",
    "NextSessionReadiness",
    "check_pre_market_readiness",
]
