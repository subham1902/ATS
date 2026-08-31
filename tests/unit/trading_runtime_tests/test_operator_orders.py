from datetime import UTC, datetime, time, timedelta
from decimal import Decimal
from uuid import uuid4

from ats.market.calendar.models import SessionCalendar
from ats.market.derivatives.contract_master import (
    DerivativeInstrumentType,
    DerivativeUnderlying,
    OptionType,
)
from ats.market.derivatives.normalization import NormalizedDerivativeContract
from ats.market.derivatives.reference_authority import InstrumentReferenceAuthority
from ats.trading_runtime.a2_runner import A2PaperSessionConfig, A2PaperSessionController
from ats.trading_runtime.broker import InMemoryMarketFeed, PaperBrokerAdapter
from ats.trading_runtime.engine import RuntimeConfig, RuntimeEvent, RuntimeEventKind, TradingRuntime
from ats.trading_runtime.lot_size import LotSizeRegistry
from ats.trading_runtime.operator_orders import (
    A04OperatorDecision,
    OperatorOrderIntent,
    OperatorOrderService,
)
from ats.trading_runtime.position_monitor import ManagedExitMode, PositionOrigin
from ats.trading_runtime.runtime_checkpoint import MemoryRuntimeCheckpointStore
from ats.trading_runtime.runtime_provider import RuntimeProviderState
from ats.trading_runtime.session import RuntimeSessionPhase

NOW = datetime(2026, 8, 28, 6, 0, tzinfo=UTC)
KEY = "NSE_FO|provider-option-key"


def _contract(source_as_of: datetime = NOW) -> NormalizedDerivativeContract:
    return NormalizedDerivativeContract(
        schema_version="1.0",
        instrument_id=uuid4(),
        exchange="NSE",
        segment="NSE_FO",
        underlying=DerivativeUnderlying.NIFTY,
        instrument_type=DerivativeInstrumentType.OPTIDX,
        expiry="2026-09-03",
        strike=Decimal("25000"),
        option_type=OptionType.CE,
        lot_size=50,
        tick_size=Decimal("0.05"),
        freeze_quantity=1800,
        weekly=True,
        tradable=True,
        provider="UPSTOX",
        provider_underlying="NIFTY",
        provider_instrument_key=KEY,
        provider_exchange_token="123",
        provider_trading_symbol="NIFTY26SEP25000CE",
        source_as_of=source_as_of,
        provider_source_hash="a" * 64,
        reference_source_hash="b" * 64,
        contract_hash="c" * 64,
    )


def _runtime(
    feed: InMemoryMarketFeed,
    broker: PaperBrokerAdapter,
    checkpoint: MemoryRuntimeCheckpointStore | None = None,
) -> TradingRuntime:
    calendar = SessionCalendar(
        calendar_id="TEST",
        calendar_version="1",
        timezone="Asia/Kolkata",
        trading_dates=(NOW.date(),),
        preopen_start=time(9),
        market_open=time(9, 15),
        market_close=time(15, 30),
        overrides=(),
    )
    return TradingRuntime(
        config=RuntimeConfig(calendar=calendar),
        market_feed=feed,
        broker=broker,
        runtime_checkpoint=checkpoint,
    )


def _service(*, a04_allow: bool = True, source_as_of: datetime = NOW):
    feed = InMemoryMarketFeed()
    feed.set_mark(KEY, Decimal("100"), NOW)
    lots = LotSizeRegistry()
    lots.register(KEY, 50)
    broker = PaperBrokerAdapter(lot_size_registry=lots)
    runtime = _runtime(feed, broker)
    state = RuntimeProviderState(
        phase=RuntimeSessionPhase.ENTRY_ALLOWED,
        can_enter=True,
        can_reduce=True,
        available=Decimal("100000"),
    )
    service = OperatorOrderService(
        references=InstrumentReferenceAuthority(
            contracts=(_contract(source_as_of),),
            retrieved_at=source_as_of,
            maximum_age=timedelta(minutes=30),
        ),
        market_feed=feed,
        broker=broker,
        runtime=runtime,
        runtime_state=lambda: state,
        a04=lambda intent, capital: A04OperatorDecision(
            allowed=a04_allow,
            decision_id=uuid4(),
            token_id=uuid4() if a04_allow else None,
            reason_codes=("A04_OPERATOR_ALLOW",) if a04_allow else ("A04_POLICY_DENY",),
        ),
    )
    return service, runtime


def _intent(**updates: object) -> OperatorOrderIntent:
    values = dict(
        operator_action_id=uuid4(),
        instrument_key=KEY,
        underlying="NIFTY",
        expiry="2026-09-03",
        strike=Decimal("25000"),
        option_type="CE",
        side="BUY",
        lots=1,
        quantity=Decimal("50"),
        order_type="LIMIT",
        requested_price=Decimal("100"),
        origin="OPERATOR_MANUAL",
        requested_at=NOW,
        managed_exit_mode=ManagedExitMode.MONITOR_ONLY,
    )
    values.update(updates)
    return OperatorOrderIntent.model_validate(values)


def test_manual_order_is_governed_and_adopted_into_canonical_position() -> None:
    service, runtime = _service()
    result = service.submit(_intent())
    assert result.accepted and result.token_id and result.paper_order_id and result.fill_id
    position = runtime.state.open_positions[str(result.position_id)]
    assert position.instrument_id == KEY
    assert position.origin is PositionOrigin.OPERATOR_MANUAL
    assert position.managed_exit_mode is ManagedExitMode.MONITOR_ONLY
    assert position.capital_committed == Decimal("5000")


def test_manual_order_cannot_bypass_reference_lot_freshness_capital_or_a04() -> None:
    service, _ = _service()
    assert "INVALID_LOT_QUANTITY" in service.submit(_intent(quantity=Decimal("49"))).reason_codes
    service.market_feed.set_mark(KEY, Decimal("100"), NOW - timedelta(minutes=1))  # type: ignore[attr-defined]
    assert "OPTION_QUOTE_STALE" in service.submit(_intent()).reason_codes
    service, _ = _service(a04_allow=False)
    assert "A04_DENY" in service.submit(_intent()).reason_codes
    service, _ = _service()
    service.runtime_state().available = Decimal("10")  # type: ignore[attr-defined]
    assert "INSUFFICIENT_CAPITAL" in service.submit(_intent()).reason_codes


def test_monitor_only_blocks_policy_exit_but_not_mandatory_session_flatten() -> None:
    service, runtime = _service()
    result = service.submit(_intent())
    position = runtime.state.open_positions[str(result.position_id)]
    runtime.state.open_positions[str(result.position_id)] = position.__class__(
        **{**position.__dict__, "thesis_healthy": False}
    )
    outcome = runtime.process_event(
        RuntimeEvent(kind=RuntimeEventKind.TICK, instrument_id=KEY, payload={}, at=NOW)
    )
    assert outcome.get("exits") is None
    runtime.state.open_positions[str(result.position_id)] = position.__class__(
        **{
            **runtime.state.open_positions[str(result.position_id)].__dict__,
            "managed_exit_mode": ManagedExitMode.ATS_MANAGED_EXIT,
        }
    )
    outcome = runtime.process_event(
        RuntimeEvent(kind=RuntimeEventKind.TICK, instrument_id=KEY, payload={}, at=NOW)
    )
    assert outcome["exits"][0]["position_id"] == str(result.position_id)


def test_manual_position_origin_and_managed_exit_survive_runtime_restart() -> None:
    checkpoint = MemoryRuntimeCheckpointStore()
    feed = InMemoryMarketFeed()
    feed.set_mark(KEY, Decimal("100"), NOW)
    lots = LotSizeRegistry()
    lots.register(KEY, 50)
    broker = PaperBrokerAdapter(lot_size_registry=lots)
    runtime = _runtime(feed, broker, checkpoint)
    position_id = "manual-position-1"
    runtime.handle_fill(
        position_id,
        Decimal("100"),
        Decimal("50"),
        NOW,
        instrument_id=KEY,
        lot_size=50,
        origin=PositionOrigin.OPERATOR_MANUAL,
        managed_exit_mode=ManagedExitMode.ATS_MANAGED_EXIT,
        operator_action_id="operator-action-1",
    )

    recovered = _runtime(feed, broker, checkpoint)
    assert tuple(recovered.state.open_positions) == (position_id,)
    position = recovered.state.open_positions[position_id]
    assert position.origin is PositionOrigin.OPERATOR_MANUAL
    assert position.managed_exit_mode is ManagedExitMode.ATS_MANAGED_EXIT
    assert position.quantity == Decimal("50")
    assert position.capital_committed == Decimal("5000")
    assert position.operator_action_id == "operator-action-1"


def test_manual_and_autonomous_positions_restore_without_order_replay() -> None:
    checkpoint = MemoryRuntimeCheckpointStore()
    feed = InMemoryMarketFeed()
    feed.set_mark(KEY, Decimal("100"), NOW)
    lots = LotSizeRegistry()
    lots.register(KEY, 50)
    broker = PaperBrokerAdapter(lot_size_registry=lots)
    runtime = _runtime(feed, broker, checkpoint)
    runtime.handle_fill(
        "manual-position",
        Decimal("100"),
        Decimal("50"),
        NOW,
        instrument_id=KEY,
        lot_size=50,
        origin=PositionOrigin.OPERATOR_MANUAL,
        managed_exit_mode=ManagedExitMode.MONITOR_ONLY,
    )
    runtime.handle_fill(
        "autonomous-position",
        Decimal("100"),
        Decimal("50"),
        NOW,
        instrument_id=KEY,
        lot_size=50,
        origin=PositionOrigin.ATS_AUTONOMOUS,
        managed_exit_mode=ManagedExitMode.ATS_MANAGED_EXIT,
    )

    recovered = _runtime(feed, broker, checkpoint)
    assert set(recovered.state.open_positions) == {"manual-position", "autonomous-position"}
    manual_pos = recovered.state.open_positions["manual-position"]
    auto_pos = recovered.state.open_positions["autonomous-position"]
    assert manual_pos.origin is PositionOrigin.OPERATOR_MANUAL
    assert manual_pos.managed_exit_mode is ManagedExitMode.MONITOR_ONLY
    assert auto_pos.origin is PositionOrigin.ATS_AUTONOMOUS
    assert sum(
        position.capital_committed for position in recovered.state.open_positions.values()
    ) == Decimal("10000")
    assert broker.query_open_orders() == ()


def test_a2_autonomous_controller_registers_lot_truth_without_manual_order_seam() -> None:
    controller = A2PaperSessionController(config=A2PaperSessionConfig())
    assert controller.start(require_token=False)
    references = InstrumentReferenceAuthority(
        contracts=(_contract(),),
        retrieved_at=NOW,
        maximum_age=timedelta(minutes=30),
    )
    controller.attach_operator_reference_authority(references)
    assert controller.operator_order_service is None
    registry = controller.broker._lot_size_registry
    assert registry is not None
    assert registry.lot_size_for(KEY) == 50
    controller.stop()
