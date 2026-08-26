from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from ats.trading_runtime.position_monitor import (
    MonitoredPosition,
    PositionAction,
    PositionMonitorConfig,
    evaluate_position,
)


def _base_pos(
    *,
    entry_price: Decimal = Decimal("200"),
    current_mark: Decimal = Decimal("200"),
    quantity: Decimal = Decimal("25"),
    capital_at_risk: Decimal = Decimal("50000"),
    entry_iv: float | None = None,
    greeks_iv: float | None = None,
    greeks_theta: float | None = None,
    expected_edge_r: float = 0.20,
    time_held_minutes: int = 0,
) -> MonitoredPosition:
    unrealized = (current_mark - entry_price) * quantity
    return MonitoredPosition(
        position_id="NIFTY:CE:1",
        instrument_id="NIFTY",
        entry_price=entry_price,
        current_mark=current_mark,
        quantity=quantity,
        realized_pnl=Decimal("0"),
        unrealized_pnl=unrealized,
        peak_pnl=max(Decimal("0"), unrealized),
        current_stop=None,
        trailing_stop=None,
        time_held_minutes=time_held_minutes,
        entry_thesis_ref=None,
        thesis_healthy=True,
        data_fresh=True,
        last_event="FILL",
        capital_at_risk=capital_at_risk,
        entry_iv=entry_iv,
        greeks_iv=greeks_iv,
        greeks_theta=greeks_theta,
        expected_edge_r=expected_edge_r,
    )


def test_capital_weighted_stop_calculation() -> None:
    now = datetime.now(UTC)
    config = PositionMonitorConfig(hard_loss_fraction=Decimal("0.015"))  # 1.5% stop

    # Capital at risk = 50,000. 1.5% loss = 750.
    # Quantity = 25. Loss per unit = 750 / 25 = 30 points.
    # If mark drops by 10 points (250 loss / 50,000 = 0.5%), position should HOLD:
    pos_holding = _base_pos(current_mark=Decimal("190"))
    dec_holding = evaluate_position(
        config=config, position=pos_holding, hwm=None, evaluation_time=now
    )
    assert dec_holding.action == PositionAction.HOLD

    # If mark drops by 35 points (875 loss / 50,000 = 1.75% > 1.5%), position should EXIT:
    pos_breach = _base_pos(current_mark=Decimal("165"))
    dec_breach = evaluate_position(
        config=config, position=pos_breach, hwm=None, evaluation_time=now
    )
    assert dec_breach.action == PositionAction.EXIT
    assert "HARD_LOSS_BREACH" in dec_breach.reason_codes


def test_iv_collapse_exit() -> None:
    now = datetime.now(UTC)
    config = PositionMonitorConfig(iv_collapse_exit_fraction=0.30)  # 30% IV drop

    # Entry IV = 0.20, Current IV = 0.13 (35% collapse)
    pos = _base_pos(entry_iv=0.20, greeks_iv=0.13)
    dec = evaluate_position(config=config, position=pos, hwm=None, evaluation_time=now)
    assert dec.action == PositionAction.EXIT
    assert "IV_COLLAPSE" in dec.reason_codes

    # Entry IV = 0.20, Current IV = 0.18 (10% drop, within tolerance)
    pos_ok = _base_pos(entry_iv=0.20, greeks_iv=0.18)
    dec_ok = evaluate_position(config=config, position=pos_ok, hwm=None, evaluation_time=now)
    assert dec_ok.action == PositionAction.HOLD


def test_theta_decay_excessive_exit() -> None:
    now = datetime.now(UTC)
    config = PositionMonitorConfig(theta_bleed_exit_fraction=0.50)

    # Position held for 180 minutes with severe theta decay
    # Daily theta = -50 per lot, quantity = 25
    pos = _base_pos(
        greeks_theta=-50.0,
        expected_edge_r=0.01,  # low edge: 0.01 * 50,000 = 500 capital edge
        time_held_minutes=200,  # 200/390 * 1250 = ~641 bleed > 250 (50% of 500)
    )
    dec = evaluate_position(config=config, position=pos, hwm=None, evaluation_time=now)
    assert dec.action == PositionAction.EXIT
    assert "THETA_DECAY_EXCESSIVE" in dec.reason_codes
