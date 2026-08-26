"""End-to-end offline integration and release validation for ATS Control Plane (O8)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from ats.contracts.domain import MarketSnapshot
from ats.contracts.domain.hashing import compute_payload_hash
from ats.contracts.domain.types import (
    DataQualityState,
    LossState,
    SessionState,
    Side,
)
from ats.contracts.governance.models import OpportunityCandidate
from ats.contracts.governance.types import CandidateStatus
from ats.contracts.intelligence.models import MarketContext
from ats.contracts.intelligence.types import LiquidityState, VolatilityState
from ats.intelligence.agent_governance import (
    RuntimeChangeCategory,
    RuntimeChangeGovernor,
    RuntimeChangeOutcome,
    RuntimeChangeProposal,
    RuntimeChangeType,
)
from ats.intelligence.research.engine import ResearchBrainEngine
from ats.portfolio.brain.engine import PortfolioManagerBrain
from ats.portfolio.brain.models import (
    AllocationOutcome,
    CandidateAllocationRequest,
    ExposureDirection,
    PortfolioBrainContext,
)
from ats.portfolio.persistence import PortfolioCapitalAccount
from ats.portfolio.runtime import PortfolioAuthoritySnapshot
from ats.trading_runtime.broker import LotSizeRegistry, OrderRequest, PaperBrokerAdapter
from ats.trading_runtime.hwm import HWMState, ProfitProtectionState
from ats.trading_runtime.intelligence_pipeline import (
    IntelligencePipelineConfig,
    MarketIntelligencePipeline,
)
from ats.trading_runtime.modes import TradingMode
from ats.trading_runtime.position_monitor import (
    MonitoredPosition,
    PositionAction,
    PositionMonitorConfig,
    evaluate_position,
    update_mark,
)

NOW = datetime(2026, 8, 24, 4, 0, tzinfo=UTC)
PORTFOLIO_ID = UUID("71000000-0000-0000-0000-000000000001")
CAMPAIGN_ID = UUID("71000000-0000-0000-0000-000000000002")
STRATEGY_ID = UUID("71000000-0000-0000-0000-000000000003")


class FakeClock:
    def __init__(self) -> None:
        self.value = NOW

    def now(self) -> datetime:
        return self.value


def _sample_snapshots() -> tuple[MarketSnapshot, ...]:
    base_time = datetime(2024, 6, 3, 5, 0, 0, tzinfo=UTC)
    snapshots = []
    prices = [
        (Decimal("100"), Decimal("102"), Decimal("99"), Decimal("101"), Decimal("1000")),
        (Decimal("101"), Decimal("103"), Decimal("100"), Decimal("102"), Decimal("1200")),
        (Decimal("102"), Decimal("104"), Decimal("101"), Decimal("103"), Decimal("1500")),
        (Decimal("103"), Decimal("106"), Decimal("102"), Decimal("105"), Decimal("2000")),
        (Decimal("105"), Decimal("108"), Decimal("104"), Decimal("107"), Decimal("2500")),
    ]
    for i, (op, hi, lo, cl, vol) in enumerate(prices):
        t = base_time + timedelta(minutes=5 * i)
        s = MarketSnapshot(
            schema_version="1.0",
            snapshot_id=uuid4(),
            instrument_id="NIFTY",
            exchange="NSE",
            segment="CASH",
            timeframe="5m",
            sequence=i + 1,
            bar_timestamp=t,
            received_at=t,
            open=op,
            high=hi,
            low=lo,
            close=cl,
            volume=vol,
            quality_state=DataQualityState.GOOD,
            quality_flags=(),
            source="feed",
            source_version="1.0.0",
            session_state=SessionState.OPEN,
            payload_hash="0" * 64,
        )
        snapshots.append(s.model_copy(update={"payload_hash": compute_payload_hash(s)}))
    return tuple(snapshots)


def _make_proposal(
    kind: RuntimeChangeType,
    *,
    category: RuntimeChangeCategory = RuntimeChangeCategory.BOUNDED_RUNTIME_CONFIG,
    current: dict[str, object] | None = None,
    proposed: dict[str, object] | None = None,
) -> RuntimeChangeProposal:
    draft = RuntimeChangeProposal(
        proposal_id=uuid4(),
        agent_id="research-agent",
        session_id=uuid4(),
        created_at=NOW,
        as_of=NOW,
        data_cutoff=NOW,
        category=category,
        proposal_type=kind,
        target="runtime",
        requested_change={"kind": kind.value},
        current_value=current or {},
        proposed_value=proposed or {},
        reason="evidence-bound request",
        evidence_refs=(uuid4(),),
        input_hash="a" * 64,
        valid_until=NOW + timedelta(minutes=1),
        payload_hash="0" * 64,
    )
    return draft.model_copy(update={"payload_hash": compute_payload_hash(draft)})


def test_offline_end_to_end_flow() -> None:
    """Validate full offline data pipeline:

    Snapshots -> Intelligence Pipeline -> Candidate -> Portfolio Brain
    -> Paper Broker -> Position Monitor -> R&D Brain
    """
    # 1. Market Snapshots & Context
    snapshots = _sample_snapshots()
    cutoff_snap = snapshots[-1]
    market_context = MarketContext(
        schema_version="1.0",
        market_context_id=uuid4(),
        instrument_spec_id=uuid4(),
        instrument_id="NIFTY",
        timeframe="5m",
        snapshot_id=cutoff_snap.snapshot_id,
        feature_bundle_id=uuid4(),
        as_of_time=cutoff_snap.received_at,
        data_cutoff=cutoff_snap.received_at,
        session_state=SessionState.OPEN,
        data_quality_state=DataQualityState.GOOD,
        freshness_ms=100,
        liquidity_state=LiquidityState.NORMAL,
        volatility_state=VolatilityState.NORMAL,
        higher_timeframe_context_refs=(),
        related_market_context_refs=(),
        cost_model_version="1.0.0",
        input_hash="0" * 64,
        payload_hash="0" * 64,
    )
    market_context = market_context.model_copy(
        update={"payload_hash": compute_payload_hash(market_context)}
    )

    # 2. Intelligence Pipeline Evaluation
    pipeline = MarketIntelligencePipeline(config=IntelligencePipelineConfig())
    eval_res = pipeline.evaluate(
        snapshots=snapshots,
        cutoff_sequence=5,
        market_context=market_context,
        campaign_id=CAMPAIGN_ID,
        strategy_id=STRATEGY_ID,
        evaluation_time=cutoff_snap.received_at,
    )
    assert eval_res.is_actionable
    assert eval_res.candidate is not None
    candidate = eval_res.candidate

    # 3. Portfolio Manager Brain Allocation
    portfolio_brain = PortfolioManagerBrain()
    account = PortfolioCapitalAccount(
        portfolio_id=PORTFOLIO_ID,
        version=1,
        total_capital=Decimal("500000"),
        deployable_capital=Decimal("500000"),
        reserved_capital=Decimal("0"),
        used_capital=Decimal("0"),
        available_capital=Decimal("500000"),
        realized_pnl=Decimal("0"),
        unrealized_pnl=Decimal("0"),
        daily_loss=Decimal("0"),
        maximum_drawdown=Decimal("0"),
        loss_state=LossState.NORMAL,
        updated_at=NOW,
    )
    hwm = HWMState(
        session_start_equity=Decimal("500000"),
        peak_equity=Decimal("500000"),
        current_equity=Decimal("500000"),
        drawdown_fraction=Decimal("0"),
        peak_profit=Decimal("0"),
        giveback_from_peak=Decimal("0"),
        profit_protection=ProfitProtectionState.NONE,
        mode_hint=None,
    )
    ctx = PortfolioBrainContext(
        snapshot=PortfolioAuthoritySnapshot(
            account=account,
            active_reservations=(),
            partition_usage=(),
            inflight_capital=Decimal("0"),
            open_risk_capital=Decimal("0"),
            active_reservation_count=0,
        ),
        positions=(),
        hwm=hwm,
        user_mode=TradingMode.NORMAL,
        effective_mode=TradingMode.NORMAL,
        feed_healthy=True,
        execution_healthy=True,
        calibration_healthy=True,
        loss_streak=0,
        remaining_session_risk=Decimal("50000"),
        as_of=NOW,
        input_hash="0" * 64,
    )
    ctx = ctx.model_copy(update={"input_hash": compute_payload_hash(ctx, hash_field="input_hash")})

    req = CandidateAllocationRequest(
        candidate=candidate,
        underlying="NIFTY",
        direction=ExposureDirection.BULLISH,
        requested_capital=Decimal("50000"),
        requested_quantity=Decimal("50"),  # Valid lot (25 * 2)
        maximum_loss=Decimal("5000"),
        expected_net_value=Decimal("50"),
        spread_fraction=Decimal("0.01"),
        liquidity_score=Decimal("0.90"),
        quote_fresh=True,
    )
    alloc_decision = portfolio_brain.allocate(req, ctx)
    assert alloc_decision.outcome in (AllocationOutcome.ALLOW, AllocationOutcome.ALLOW_REDUCED)
    assert alloc_decision.approved_capital > 0

    # 4. Paper Broker Execution with Lot Sizing & Slippage
    paper_broker = PaperBrokerAdapter(
        healthy=True,
        lot_size_registry=LotSizeRegistry({"NIFTY_CE": 25}),
        base_slippage_ticks=1,
        tick_size=Decimal("0.05"),
    )
    slipped_price = paper_broker.apply_slippage(Decimal("100.00"), "BUY")
    assert slipped_price == Decimal("100.05")

    order_req = OrderRequest(
        instrument_id="NIFTY_CE",
        side="BUY",
        quantity=Decimal("50"),
        order_type="LIMIT",
        limit_price=slipped_price,
        idempotency_key=str(uuid4()),
        intent_id=str(candidate.candidate_id),
    )
    order_res = paper_broker.submit_order(order_req, now=NOW)
    assert order_res is not None
    assert order_res.status == "ACKNOWLEDGED"

    # Process fill
    paper_broker.seed_fill(order_res.order_id, slipped_price, Decimal("50"), now=NOW)
    fill_status = paper_broker.query_order(order_res.order_id)
    assert fill_status is not None
    assert fill_status.status == "FILLED"
    assert fill_status.filled_quantity == Decimal("50")

    # 5. Position Monitor with Live Mark and Capital Stop
    pos = MonitoredPosition(
        position_id=str(uuid4()),
        instrument_id="NIFTY_CE",
        entry_price=slipped_price,
        current_mark=slipped_price,
        quantity=fill_status.filled_quantity,
        realized_pnl=Decimal("0"),
        unrealized_pnl=Decimal("0"),
        peak_pnl=Decimal("0"),
        current_stop=slipped_price * Decimal("0.95"),
        trailing_stop=None,
        time_held_minutes=0,
        entry_thesis_ref=str(candidate.thesis_id),
        thesis_healthy=True,
        data_fresh=True,
        last_event=None,
        capital_at_risk=Decimal("5000"),
    )
    monitor_cfg = PositionMonitorConfig(hard_loss_fraction=Decimal("0.05"))

    # Price rises to 105 -> HOLD
    pos_up = update_mark(pos, mark=Decimal("105.00"), at=NOW + timedelta(minutes=5))
    dec_up = evaluate_position(
        config=monitor_cfg, position=pos_up, hwm=hwm, evaluation_time=NOW + timedelta(minutes=5)
    )
    assert dec_up.action in (PositionAction.HOLD, PositionAction.TRAIL)
    assert not dec_up.should_exit_now

    # Price drops to 85 -> Capital stop breach -> EXIT
    pos_down = update_mark(pos, mark=Decimal("85.00"), at=NOW + timedelta(minutes=10))
    dec_down = evaluate_position(
        config=monitor_cfg,
        position=pos_down,
        hwm=hwm,
        evaluation_time=NOW + timedelta(minutes=10),
    )
    assert dec_down.action is PositionAction.EXIT
    assert dec_down.should_exit_now
    assert "HARD_LOSS_BREACH" in dec_down.reason_codes

    # 6. R&D Brain Hypothesis and Experiment Formulation
    rd_brain = ResearchBrainEngine()
    hyp = rd_brain.create_hypothesis(
        question="Does momentum persistence improve when VIX is elevated?",
        rationale="Volatile opening regimes exhibit higher breakout follow-through.",
        evidence_refs=(candidate.candidate_id,),
        market_regime_scope=("HIGH_VOLATILITY",),
        dataset_scope="NSE_NIFTY_2024",
        as_of=NOW,
    )
    assert hyp.hypothesis_id is not None
    assert hyp.payload_hash == compute_payload_hash(hyp)


def test_agent_governance_rules() -> None:
    """Validate RuntimeChangeGovernor strict safety gates."""
    governor = RuntimeChangeGovernor(clock=FakeClock())

    # 1. Proposing SAFE mode -> APPROVED & APPLIED
    prop_safe = _make_proposal(
        RuntimeChangeType.SET_SAFE_MODE,
        proposed={"mode": "SAFE"},
    )
    dec_safe = governor.evaluate(prop_safe, effective_mode=TradingMode.AGGRESSIVE)
    assert dec_safe.outcome is RuntimeChangeOutcome.APPLY

    # 2. Proposing AGGRESSIVE auto-escalation -> REJECTED
    prop_agg = _make_proposal(
        RuntimeChangeType.SET_AGGRESSIVE_MODE,
        proposed={"mode": "AGGRESSIVE"},
    )
    dec_agg = governor.evaluate(prop_agg, effective_mode=TradingMode.NORMAL)
    assert dec_agg.outcome is RuntimeChangeOutcome.REJECT

    # 3. Proposing Hard-Risk Increase -> REJECTED
    prop_risk = _make_proposal(
        RuntimeChangeType.INCREASE_HARD_RISK,
        category=RuntimeChangeCategory.FINANCIAL_AUTHORITY,
        proposed={"amount": "100000"},
    )
    dec_risk = governor.evaluate(prop_risk, effective_mode=TradingMode.NORMAL)
    assert dec_risk.outcome is RuntimeChangeOutcome.REJECT

    # 4. Proposing Strategy Experiment -> ACCEPTED into research queue
    prop_exp = _make_proposal(
        RuntimeChangeType.CREATE_HYPOTHESIS,
        category=RuntimeChangeCategory.RESEARCH_STATE,
        proposed={"hypothesis": "Test"},
    )
    dec_exp = governor.evaluate(prop_exp, effective_mode=TradingMode.NORMAL)
    assert dec_exp.outcome is RuntimeChangeOutcome.APPLY

    # 5. Proposing Direct Order Placement -> REJECTED (Zero financial authority)
    prop_order = _make_proposal(
        RuntimeChangeType.PLACE_ORDER,
        category=RuntimeChangeCategory.FINANCIAL_AUTHORITY,
        proposed={"symbol": "NIFTY", "qty": 50},
    )
    dec_order = governor.evaluate(prop_order, effective_mode=TradingMode.NORMAL)
    assert dec_order.outcome is RuntimeChangeOutcome.REJECT


def test_failure_injection_resilience() -> None:
    """Prove that failures in advisory/Harness/dashboard/LLM do not compromise P0/P1 safety."""
    # 1. PositionMonitor continues executing safely even if advisory fails
    pos = MonitoredPosition(
        position_id=str(uuid4()),
        instrument_id="NIFTY_CE",
        entry_price=Decimal("100.00"),
        current_mark=Decimal("94.00"),  # Below 5% stop
        quantity=Decimal("50"),
        realized_pnl=Decimal("-300"),
        unrealized_pnl=Decimal("-300"),
        peak_pnl=Decimal("0"),
        current_stop=Decimal("95.00"),
        trailing_stop=None,
        time_held_minutes=1,
        entry_thesis_ref="test",
        thesis_healthy=True,
        data_fresh=True,
        last_event=None,
        capital_at_risk=Decimal("5000"),
    )
    monitor_cfg = PositionMonitorConfig(hard_loss_fraction=Decimal("0.05"))
    # Even in complete isolation, stop loss triggers deterministically
    decision = evaluate_position(config=monitor_cfg, position=pos, hwm=None, evaluation_time=NOW)
    assert decision.action is PositionAction.EXIT
    assert decision.should_exit_now
    assert "HARD_LOSS_BREACH" in decision.reason_codes

    # 2. Portfolio Brain denies safely if feed or execution is unhealthy
    brain = PortfolioManagerBrain()
    account = PortfolioCapitalAccount(
        portfolio_id=PORTFOLIO_ID,
        version=1,
        total_capital=Decimal("500000"),
        deployable_capital=Decimal("500000"),
        reserved_capital=Decimal("0"),
        used_capital=Decimal("0"),
        available_capital=Decimal("500000"),
        realized_pnl=Decimal("0"),
        unrealized_pnl=Decimal("0"),
        daily_loss=Decimal("0"),
        maximum_drawdown=Decimal("0"),
        loss_state=LossState.NORMAL,
        updated_at=NOW,
    )
    ctx_unhealthy_feed = PortfolioBrainContext(
        snapshot=PortfolioAuthoritySnapshot(
            account=account,
            active_reservations=(),
            partition_usage=(),
            inflight_capital=Decimal("0"),
            open_risk_capital=Decimal("0"),
            active_reservation_count=0,
        ),
        positions=(),
        hwm=HWMState(
            session_start_equity=Decimal("500000"),
            peak_equity=Decimal("500000"),
            current_equity=Decimal("500000"),
            drawdown_fraction=Decimal("0"),
            peak_profit=Decimal("0"),
            giveback_from_peak=Decimal("0"),
            profit_protection=ProfitProtectionState.NONE,
            mode_hint=None,
        ),
        user_mode=TradingMode.NORMAL,
        effective_mode=TradingMode.NORMAL,
        feed_healthy=False,  # Injected failure
        execution_healthy=True,
        calibration_healthy=True,
        loss_streak=0,
        remaining_session_risk=Decimal("50000"),
        as_of=NOW,
        input_hash="0" * 64,
    )
    ctx_unhealthy_feed = ctx_unhealthy_feed.model_copy(
        update={"input_hash": compute_payload_hash(ctx_unhealthy_feed, hash_field="input_hash")}
    )

    cand = OpportunityCandidate(
        schema_version="1.0",
        candidate_id=uuid4(),
        candidate_version=1,
        instrument_id="NIFTY_CE",
        market_context_id=uuid4(),
        thesis_id=uuid4(),
        thesis_version=1,
        distribution_id=uuid4(),
        campaign_id=CAMPAIGN_ID,
        campaign_version=1,
        strategy_definition_id=STRATEGY_ID,
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
    cand = cand.model_copy(update={"payload_hash": compute_payload_hash(cand)})

    req = CandidateAllocationRequest(
        candidate=cand,
        underlying="NIFTY",
        direction=ExposureDirection.BULLISH,
        requested_capital=Decimal("50000"),
        requested_quantity=Decimal("50"),
        maximum_loss=Decimal("5000"),
        expected_net_value=Decimal("50"),
        spread_fraction=Decimal("0.01"),
        liquidity_score=Decimal("0.90"),
        quote_fresh=True,
    )

    alloc_denial = brain.allocate(req, ctx_unhealthy_feed)
    assert alloc_denial.outcome is AllocationOutcome.DENY
    assert "MARKET_DATA_UNSAFE" in alloc_denial.reason_codes
