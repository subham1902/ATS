"""Comprehensive unit tests for Portfolio Manager Brain (O6)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from ats.contracts.domain.hashing import compute_payload_hash
from ats.contracts.domain.types import LossState, Side
from ats.contracts.governance.models import OpportunityCandidate
from ats.contracts.governance.types import CandidateStatus
from ats.portfolio.brain.engine import PortfolioManagerBrain
from ats.portfolio.brain.models import (
    AllocationOutcome,
    CandidateAllocationRequest,
    ExposureDirection,
    PortfolioBrainContext,
    PortfolioReviewAction,
    PositionExposure,
)
from ats.portfolio.persistence import PortfolioCapitalAccount
from ats.portfolio.runtime import PortfolioAuthoritySnapshot
from ats.trading_runtime.hwm import HWMState, ProfitProtectionState
from ats.trading_runtime.modes import TradingMode

NOW = datetime(2026, 8, 24, 4, 0, tzinfo=UTC)
PORTFOLIO_ID = UUID("71000000-0000-0000-0000-000000000001")
CAMPAIGN_ID = UUID("71000000-0000-0000-0000-000000000002")
STRATEGY_ID = UUID("71000000-0000-0000-0000-000000000003")


def _account(
    total: str = "500000",
    available: str = "500000",
    loss_state: LossState = LossState.NORMAL,
) -> PortfolioCapitalAccount:
    return PortfolioCapitalAccount(
        portfolio_id=PORTFOLIO_ID,
        version=1,
        total_capital=Decimal(total),
        deployable_capital=Decimal(total),
        reserved_capital=Decimal("0"),
        used_capital=Decimal("0"),
        available_capital=Decimal(available),
        realized_pnl=Decimal("0"),
        unrealized_pnl=Decimal("0"),
        daily_loss=Decimal("0"),
        maximum_drawdown=Decimal("0"),
        loss_state=loss_state,
        updated_at=NOW,
    )


def _snapshot(account: PortfolioCapitalAccount | None = None) -> PortfolioAuthoritySnapshot:
    acc = account or _account()
    return PortfolioAuthoritySnapshot(
        account=acc,
        active_reservations=(),
        partition_usage=(),
        inflight_capital=Decimal("0"),
        open_risk_capital=Decimal("0"),
        active_reservation_count=0,
    )


def _hwm(
    drawdown_fraction: float = 0.0,
    profit_protection: ProfitProtectionState = ProfitProtectionState.NONE,
    mode_hint: TradingMode | None = None,
) -> HWMState:
    start = Decimal("100000")
    peak = Decimal("110000")
    giveback = Decimal("10000") * Decimal(str(drawdown_fraction))
    current = peak - giveback
    return HWMState(
        session_start_equity=start,
        peak_equity=peak,
        current_equity=current,
        drawdown_fraction=Decimal(str(drawdown_fraction)),
        peak_profit=Decimal("10000"),
        giveback_from_peak=giveback,
        profit_protection=profit_protection,
        mode_hint=mode_hint,
    )


def _candidate(
    instrument_id: str = "NIFTY24AUG24500CE",
    strategy_id: UUID = STRATEGY_ID,
) -> OpportunityCandidate:
    cand = OpportunityCandidate(
        schema_version="1.0",
        candidate_id=uuid4(),
        candidate_version=1,
        instrument_id=instrument_id,
        market_context_id=uuid4(),
        thesis_id=uuid4(),
        thesis_version=1,
        distribution_id=uuid4(),
        campaign_id=CAMPAIGN_ID,
        campaign_version=1,
        strategy_definition_id=strategy_id,
        strategy_definition_version=1,
        side=Side.BUY,
        event_definition_id=uuid4(),
        horizon_bars=3,
        target_outcome_code="UP",
        calibrated_probability=Decimal("0.65"),
        expected_net_edge_r=0.4,
        expected_reward_risk=Decimal("2.0"),
        entry_conditions=(),
        proposed_stop_price=Decimal("90"),
        proposed_target_price=Decimal("120"),
        evidence_refs=(uuid4(),),
        status=CandidateStatus.CREATED,
        risk_decision_id=None,
        advisory_id=None,
        autonomy_token_id=None,
        created_at=NOW,
        expires_at=NOW + timedelta(minutes=15),
        payload_hash="0" * 64,
    )
    return cand.model_copy(update={"payload_hash": compute_payload_hash(cand)})


def _context(
    *,
    positions: tuple[PositionExposure, ...] = (),
    account: PortfolioCapitalAccount | None = None,
    hwm: HWMState | None = None,
    user_mode: TradingMode = TradingMode.NORMAL,
    effective_mode: TradingMode = TradingMode.NORMAL,
    feed_healthy: bool = True,
    execution_healthy: bool = True,
    calibration_healthy: bool = True,
    loss_streak: int = 0,
    remaining_session_risk: Decimal = Decimal("50000"),
) -> PortfolioBrainContext:
    snap = _snapshot(account)
    ctx = PortfolioBrainContext(
        snapshot=snap,
        positions=positions,
        hwm=hwm or _hwm(),
        user_mode=user_mode,
        effective_mode=effective_mode,
        feed_healthy=feed_healthy,
        execution_healthy=execution_healthy,
        calibration_healthy=calibration_healthy,
        loss_streak=loss_streak,
        remaining_session_risk=remaining_session_risk,
        as_of=NOW,
        input_hash="0" * 64,
    )
    return ctx.model_copy(update={"input_hash": compute_payload_hash(ctx, hash_field="input_hash")})


def _request(
    *,
    candidate: OpportunityCandidate | None = None,
    underlying: str = "NIFTY",
    direction: ExposureDirection = ExposureDirection.BULLISH,
    requested_capital: Decimal = Decimal("50000"),
    requested_quantity: Decimal = Decimal("50"),
    maximum_loss: Decimal = Decimal("10000"),
    expected_net_value: Decimal = Decimal("50"),
    spread_fraction: Decimal = Decimal("0.01"),
    liquidity_score: Decimal = Decimal("0.90"),
    quote_fresh: bool = True,
) -> CandidateAllocationRequest:
    return CandidateAllocationRequest(
        candidate=candidate or _candidate(),
        underlying=underlying,
        direction=direction,
        requested_capital=requested_capital,
        requested_quantity=requested_quantity,
        maximum_loss=maximum_loss,
        expected_net_value=expected_net_value,
        spread_fraction=spread_fraction,
        liquidity_score=liquidity_score,
        quote_fresh=quote_fresh,
    )


def test_portfolio_brain_allow_full() -> None:
    brain = PortfolioManagerBrain()
    ctx = _context(effective_mode=TradingMode.NORMAL)
    req = _request(
        requested_capital=Decimal("50000"),
        requested_quantity=Decimal("50"),
        liquidity_score=Decimal("1.0"),
    )

    decision = brain.allocate(req, ctx)

    assert decision.outcome is AllocationOutcome.ALLOW
    assert decision.approved_capital == Decimal("50000.00")
    assert decision.approved_quantity == Decimal("50")
    assert "PORTFOLIO_ALLOCATION_PERMITTED" in decision.reason_codes
    assert decision.correlation_penalty == Decimal("0")
    assert decision.concentration_penalty == Decimal("0")
    assert decision.payload_hash == compute_payload_hash(decision)


def test_portfolio_brain_allow_reduced_correlation() -> None:
    brain = PortfolioManagerBrain()
    existing = PositionExposure(
        position_id=uuid4(),
        underlying="BANKNIFTY",
        direction=ExposureDirection.BULLISH,
        strategy_id=uuid4(),
        capital_at_risk=Decimal("50000"),
    )
    ctx = _context(positions=(existing,), effective_mode=TradingMode.NORMAL)
    req = _request(
        underlying="NIFTY",
        direction=ExposureDirection.BULLISH,
        requested_capital=Decimal("50000"),
        requested_quantity=Decimal("50"),
        maximum_loss=Decimal("5000"),
        liquidity_score=Decimal("1.0"),
    )

    decision = brain.allocate(req, ctx)

    assert decision.outcome is AllocationOutcome.ALLOW_REDUCED
    assert decision.correlation_penalty == Decimal("0.25")
    # 50,000 * (1 - 0.25) = 37,500
    assert decision.approved_capital == Decimal("37500.00")
    # 50 * (37500 / 50000) = 37
    assert decision.approved_quantity == Decimal("37")
    assert "PORTFOLIO_PENALTY_REDUCED_SIZE" in decision.reason_codes


def test_portfolio_brain_opposite_direction_no_correlation_penalty() -> None:
    brain = PortfolioManagerBrain()
    existing = PositionExposure(
        position_id=uuid4(),
        underlying="BANKNIFTY",
        direction=ExposureDirection.BEARISH,  # Opposite
        strategy_id=uuid4(),
        capital_at_risk=Decimal("50000"),
    )
    ctx = _context(positions=(existing,), effective_mode=TradingMode.NORMAL)
    req = _request(
        underlying="NIFTY",
        direction=ExposureDirection.BULLISH,
        liquidity_score=Decimal("1.0"),
    )

    decision = brain.allocate(req, ctx)

    assert decision.correlation_penalty == Decimal("0")
    assert decision.outcome is AllocationOutcome.ALLOW


def test_portfolio_brain_same_underlying_concentration() -> None:
    brain = PortfolioManagerBrain()
    existing = PositionExposure(
        position_id=uuid4(),
        underlying="NIFTY",
        direction=ExposureDirection.BEARISH,
        strategy_id=uuid4(),
        capital_at_risk=Decimal("50000"),
    )
    ctx = _context(positions=(existing,), effective_mode=TradingMode.NORMAL)
    req = _request(
        underlying="NIFTY",
        maximum_loss=Decimal("5000"),
        liquidity_score=Decimal("1.0"),
    )

    decision = brain.allocate(req, ctx)

    assert decision.concentration_penalty == Decimal("0.25")
    assert decision.outcome is AllocationOutcome.ALLOW_REDUCED


def test_portfolio_brain_same_strategy_concentration() -> None:
    brain = PortfolioManagerBrain()
    existing = PositionExposure(
        position_id=uuid4(),
        underlying="BANKNIFTY",
        direction=ExposureDirection.BEARISH,
        strategy_id=STRATEGY_ID,  # Same strategy
        capital_at_risk=Decimal("50000"),
    )
    ctx = _context(positions=(existing,), effective_mode=TradingMode.NORMAL)
    req = _request(
        underlying="NIFTY",
        maximum_loss=Decimal("5000"),
        liquidity_score=Decimal("1.0"),
    )

    decision = brain.allocate(req, ctx)

    assert decision.concentration_penalty == Decimal("0.15")
    assert decision.outcome is AllocationOutcome.ALLOW_REDUCED


def test_portfolio_brain_defer_at_max_positions() -> None:
    brain = PortfolioManagerBrain()
    p1 = PositionExposure(
        position_id=uuid4(),
        underlying="NIFTY",
        direction=ExposureDirection.BULLISH,
        strategy_id=uuid4(),
        capital_at_risk=Decimal("50000"),
    )
    # SAFE mode allows max 1 position
    ctx = _context(positions=(p1,), effective_mode=TradingMode.SAFE)
    req = _request()

    decision = brain.allocate(req, ctx)

    assert decision.outcome is AllocationOutcome.DEFER
    assert "POSITION_CAPACITY_REACHED" in decision.reason_codes
    assert decision.approved_capital == Decimal("0")
    assert decision.approved_quantity == Decimal("0")


def test_portfolio_brain_deny_insufficient_risk_budget() -> None:
    brain = PortfolioManagerBrain()
    # Only 5,000 remaining session risk, but candidate maximum loss is 10,000
    ctx = _context(remaining_session_risk=Decimal("5000"))
    req = _request(requested_capital=Decimal("50000"), maximum_loss=Decimal("10000"))

    decision = brain.allocate(req, ctx)

    assert decision.outcome is AllocationOutcome.DENY
    assert "INSUFFICIENT_RISK_BUDGET" in decision.reason_codes


def test_portfolio_brain_deny_quantity_reduced_to_zero() -> None:
    brain = PortfolioManagerBrain()
    # Drawdown 20% -> penalty = 0.80
    ctx = _context(hwm=_hwm(drawdown_fraction=0.20))
    # Requested 1 unit @ 50,000 -> approved = 10,000 -> 1 * 0.20 = 0.20 -> floor = 0
    req = _request(
        requested_capital=Decimal("50000"),
        requested_quantity=Decimal("1"),
        maximum_loss=Decimal("5000"),
    )

    decision = brain.allocate(req, ctx)

    assert decision.outcome is AllocationOutcome.DENY
    assert "QUANTITY_REDUCED_TO_ZERO" in decision.reason_codes


def test_portfolio_brain_deny_stale_quote() -> None:
    brain = PortfolioManagerBrain()
    ctx = _context()
    req = _request(quote_fresh=False)

    decision = brain.allocate(req, ctx)

    assert decision.outcome is AllocationOutcome.DENY
    assert "MARKET_DATA_UNSAFE" in decision.reason_codes


def test_portfolio_brain_deny_unhealthy_feed() -> None:
    brain = PortfolioManagerBrain()
    ctx = _context(feed_healthy=False)
    req = _request()

    decision = brain.allocate(req, ctx)

    assert decision.outcome is AllocationOutcome.DENY
    assert "MARKET_DATA_UNSAFE" in decision.reason_codes


def test_portfolio_brain_deny_unhealthy_execution() -> None:
    brain = PortfolioManagerBrain()
    ctx = _context(execution_healthy=False)
    req = _request()

    decision = brain.allocate(req, ctx)

    assert decision.outcome is AllocationOutcome.DENY
    assert "EXECUTION_UNHEALTHY" in decision.reason_codes


def test_portfolio_brain_deny_low_expected_net_value() -> None:
    brain = PortfolioManagerBrain()
    ctx = _context(effective_mode=TradingMode.NORMAL)  # Min is 10
    req = _request(expected_net_value=Decimal("5"))

    decision = brain.allocate(req, ctx)

    assert decision.outcome is AllocationOutcome.DENY
    assert "EXPECTED_NET_VALUE_TOO_LOW" in decision.reason_codes


def test_portfolio_brain_deny_spread_too_wide() -> None:
    brain = PortfolioManagerBrain()
    ctx = _context(effective_mode=TradingMode.NORMAL)  # Max spread is 0.04
    req = _request(spread_fraction=Decimal("0.08"))

    decision = brain.allocate(req, ctx)

    assert decision.outcome is AllocationOutcome.DENY
    assert "SPREAD_TOO_WIDE" in decision.reason_codes


def test_portfolio_brain_deny_liquidity_too_low() -> None:
    brain = PortfolioManagerBrain()
    ctx = _context(effective_mode=TradingMode.NORMAL)  # Min liquidity is 0.60
    req = _request(liquidity_score=Decimal("0.30"))

    decision = brain.allocate(req, ctx)

    assert decision.outcome is AllocationOutcome.DENY
    assert "LIQUIDITY_TOO_LOW" in decision.reason_codes


def test_portfolio_brain_deescalate_on_loss_streak() -> None:
    brain = PortfolioManagerBrain()
    ctx = _context(effective_mode=TradingMode.AGGRESSIVE, loss_streak=3)
    req = _request(liquidity_score=Decimal("0.90"))

    decision = brain.allocate(req, ctx)

    assert decision.effective_mode is TradingMode.SAFE
    assert "PERFORMANCE_DEGRADED" in decision.reason_codes


def test_portfolio_brain_deescalate_on_calibration_degraded() -> None:
    brain = PortfolioManagerBrain()
    ctx = _context(effective_mode=TradingMode.AGGRESSIVE, calibration_healthy=False)
    req = _request(liquidity_score=Decimal("0.90"))

    decision = brain.allocate(req, ctx)

    assert decision.effective_mode is TradingMode.SAFE
    assert "PERFORMANCE_DEGRADED" in decision.reason_codes


def test_portfolio_brain_deescalate_on_hwm_hint() -> None:
    brain = PortfolioManagerBrain()
    ctx = _context(
        effective_mode=TradingMode.AGGRESSIVE,
        hwm=_hwm(mode_hint=TradingMode.SAFE),
    )
    req = _request(liquidity_score=Decimal("0.90"))

    decision = brain.allocate(req, ctx)

    assert decision.effective_mode is TradingMode.SAFE
    assert "HWM_DEESCALATION" in decision.reason_codes


def test_portfolio_brain_halted_loss_state() -> None:
    brain = PortfolioManagerBrain()
    acc = _account(loss_state=LossState.HALTED)
    ctx = _context(account=acc)
    req = _request()

    decision = brain.allocate(req, ctx)

    assert decision.outcome is AllocationOutcome.DENY
    assert decision.effective_mode is TradingMode.HALTED
    assert "PORTFOLIO_HALTED" in decision.reason_codes


def test_portfolio_brain_no_capital_mutation() -> None:
    brain = PortfolioManagerBrain()
    acc = _account()
    original_version = acc.version
    original_available = acc.available_capital
    original_reserved = acc.reserved_capital

    ctx = _context(account=acc)
    req = _request()

    _ = brain.allocate(req, ctx)
    _ = brain.review(ctx)

    # Verifying zero mutation of capital account and authority snapshot
    assert ctx.snapshot.account.version == original_version
    assert ctx.snapshot.account.available_capital == original_available
    assert ctx.snapshot.account.reserved_capital == original_reserved
    assert len(ctx.snapshot.active_reservations) == 0


def test_portfolio_brain_review_actions() -> None:
    brain = PortfolioManagerBrain()

    # 1. Normal state -> KEEP
    ctx_normal = _context(effective_mode=TradingMode.NORMAL)
    rev_normal = brain.review(ctx_normal)
    assert rev_normal.action is PortfolioReviewAction.KEEP
    assert "PORTFOLIO_WITHIN_ENVELOPE" in rev_normal.reason_codes

    # 2. Halted -> EXIT_RECOMMENDED
    ctx_halted = _context(account=_account(loss_state=LossState.HALTED))
    rev_halted = brain.review(ctx_halted)
    assert rev_halted.action is PortfolioReviewAction.EXIT_RECOMMENDED

    # 3. Mode mismatch -> DEESCALATE_MODE
    ctx_deescalate = _context(effective_mode=TradingMode.AGGRESSIVE, loss_streak=3)
    rev_deescalate = brain.review(ctx_deescalate)
    assert rev_deescalate.action is PortfolioReviewAction.DEESCALATE_MODE
    assert rev_deescalate.effective_mode is TradingMode.SAFE

    # 4. Infrastructure degraded -> BLOCK_NEW_DIRECTION
    ctx_infra = _context(feed_healthy=False, effective_mode=TradingMode.SAFE)
    rev_infra = brain.review(ctx_infra)
    assert rev_infra.action is PortfolioReviewAction.BLOCK_NEW_DIRECTION

    # 5. Profit protection triggered -> REDUCE
    ctx_pp = _context(
        effective_mode=TradingMode.NORMAL,
        hwm=_hwm(profit_protection=ProfitProtectionState.TRIGGERED),
    )
    rev_pp = brain.review(ctx_pp)
    assert rev_pp.action is PortfolioReviewAction.REDUCE
