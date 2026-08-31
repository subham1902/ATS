"""Shared helpers for trading_runtime unit tests (autonomous paper)."""

from __future__ import annotations

from datetime import UTC, date, datetime, time
from decimal import Decimal

from ats.contracts.common import UTCDateTime
from ats.contracts.domain.types import DataQualityState
from ats.execution.paper.models import (
    PaperExecutionPolicy,
    PaperMarketFacts,
    PaperSubmissionScenario,
)
from ats.market.calendar.models import SessionCalendar
from ats.market.derivatives.contract_master import DerivativeInstrument
from ats.trading_runtime.broker import InMemoryMarketFeed, PaperBrokerAdapter
from ats.trading_runtime.orchestrator import (
    AuthorizationProvider,
    AutonomousPaperOrchestrator,
    MarketFactsProvider,
)

NIFTY = "C1"
NIFTY_FULL = "NIFTY:CE"

NOW = datetime(2026, 8, 24, 4, 0, tzinfo=UTC)


def calendar() -> SessionCalendar:
    return SessionCalendar(
        calendar_id="T",
        calendar_version="1.0.0",
        timezone="Asia/Kolkata",
        trading_dates=(date(2026, 8, 24),),
        preopen_start=time(9, 0),
        market_open=time(9, 15),
        market_close=time(15, 30),
        overrides=(),
    )


def instrument() -> DerivativeInstrument:
    from tests.unit.market.derivatives.option_chain.helpers import master

    return next(i for i in master().instruments if i.instrument_id == NIFTY)


def policy() -> PaperExecutionPolicy:
    return PaperExecutionPolicy(
        broker_model_version="DERIVATIVE-PAPER-V1",
        cost_model_version="NSE-PAPER-COST-V1",
        maximum_quote_age_ms=60000,
        slippage_ticks=2,
        fee_fraction=Decimal("0.001"),
        tax_fraction=Decimal("0.002"),
    )


def market_facts(
    *,
    instrument_id: str = NIFTY,
    bid: Decimal = Decimal("99"),
    ask: Decimal = Decimal("101"),
    bid_quantity: int = 130,
    ask_quantity: int = 130,
    at: UTCDateTime = NOW,
    scenario: PaperSubmissionScenario = PaperSubmissionScenario.ACKNOWLEDGE,
    rejection_reason: str | None = None,
) -> PaperMarketFacts:
    return PaperMarketFacts(
        instrument_id=instrument_id,
        bid=bid,
        ask=ask,
        bid_quantity=bid_quantity,
        ask_quantity=ask_quantity,
        quote_time=at,
        quality_state=DataQualityState.GOOD,
        scenario=scenario,
        rejection_reason=rejection_reason,
    )


def allow_all(result: dict) -> object:
    from ats.kernel.types import ALLOW

    _ = result
    return ALLOW


def deny_all(result: dict) -> object:
    from ats.kernel.types import GateCode, KernelOutcome, KernelResult

    _ = result
    return KernelResult(
        outcome=KernelOutcome.DENY, reason_codes=(GateCode.TOKEN_INVALID,)
    )


def build_orchestrator(
    *,
    market_facts_provider: MarketFactsProvider,
    authorization_provider: AuthorizationProvider | None = None,
    feed: InMemoryMarketFeed | None = None,
    broker: PaperBrokerAdapter | None = None,
    opening_capital: Decimal = Decimal("100000"),
    at: UTCDateTime = NOW,
    cal: SessionCalendar | None = None,
    inst: DerivativeInstrument | None = None,
    pol: PaperExecutionPolicy | None = None,
) -> AutonomousPaperOrchestrator:

    inst = inst or instrument()
    pol = pol or policy()
    broker = broker or PaperBrokerAdapter(policy=pol, instrument=inst)
    feed = feed or InMemoryMarketFeed()
    feed.set_mark("NIFTY", Decimal("25000"), at)
    feed.set_mark(inst.instrument_id, Decimal("101"), at)
    orch = AutonomousPaperOrchestrator(
        calendar=cal or calendar(),
        market_feed=feed,
        broker=broker,
        policy=pol,
        instrument=inst,
        market_facts_provider=market_facts_provider,
        authorization_provider=authorization_provider or allow_all,
        opening_capital=opening_capital,
    )
    orch.start(at)
    return orch
