from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from ats.trading_runtime.position_monitor import (
    MonitoredPosition,
    PositionAction,
    PositionMonitorConfig,
    evaluate_position,
)


def _pos(**overrides: object) -> MonitoredPosition:
    base: dict[str, object] = {
        "position_id": "NIFTY:1",
        "instrument_id": "NIFTY",
        "entry_price": Decimal("100"),
        "current_mark": Decimal("101"),
        "quantity": Decimal("75"),
        "realized_pnl": Decimal("0"),
        "unrealized_pnl": Decimal("75"),
        "peak_pnl": Decimal("75"),
        "current_stop": None,
        "trailing_stop": None,
        "time_held_minutes": 10,
        "entry_thesis_ref": None,
        "thesis_healthy": True,
        "data_fresh": True,
        "last_event": None,
    }
    base.update(overrides)
    return MonitoredPosition(**base)  # type: ignore[arg-type]


def test_hold_when_healthy() -> None:
    dec = evaluate_position(
        config=PositionMonitorConfig(), position=_pos(), hwm=None, evaluation_time=datetime.now(UTC)
    )
    assert dec.action in (PositionAction.HOLD, PositionAction.TRAIL)
    assert not dec.should_exit_now


def test_hard_loss_triggers_exit() -> None:
    dec = evaluate_position(
        config=PositionMonitorConfig(hard_loss_fraction=Decimal("0.01")),
        position=_pos(current_mark=Decimal("98")),
        hwm=None,
        evaluation_time=datetime.now(UTC),
    )
    assert dec.action == PositionAction.EXIT
    assert dec.should_exit_now


def test_trailing_stop_hit() -> None:
    dec = evaluate_position(
        config=PositionMonitorConfig(),
        position=_pos(current_mark=Decimal("99"), trailing_stop=Decimal("100")),
        hwm=None,
        evaluation_time=datetime.now(UTC),
    )
    assert dec.action == PositionAction.EXIT


def test_time_exit() -> None:
    dec = evaluate_position(
        config=PositionMonitorConfig(max_hold_minutes=5),
        position=_pos(time_held_minutes=10),
        hwm=None,
        evaluation_time=datetime.now(UTC),
    )
    assert dec.action == PositionAction.EXIT


def test_stale_mark_no_data() -> None:
    dec = evaluate_position(
        config=PositionMonitorConfig(),
        position=_pos(current_mark=None, data_fresh=False),
        hwm=None,
        evaluation_time=datetime.now(UTC),
    )
    assert dec.action == PositionAction.NO_DATA