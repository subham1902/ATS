from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from ats.market.metatrader.account_session import _sizing_quote


@pytest.fixture
def sdk(monkeypatch):
    monkeypatch.setattr(
        "ats.market.metatrader.account_session._safe_snapshot",
        lambda *args: {"free_margin": "1000"},
    )
    transport = Mock()
    transport.ORDER_TYPE_BUY = 0
    transport.ORDER_TYPE_SELL = 1
    transport.symbol_info.return_value = SimpleNamespace(
        volume_min=0.01, volume_step=0.01, volume_max=10
    )
    transport.order_calc_profit.side_effect = (
        lambda kind, symbol, volume, entry, stop: -abs(entry - stop) * 100 * volume
    )
    transport.order_calc_margin.side_effect = lambda kind, symbol, volume, entry: volume * 100
    return transport


def test_preview_floors_volume_and_includes_explicit_costs(sdk):
    result = _sizing_quote(sdk, "XAUUSD", 1, "server", "BUY", 2300, 2290, 25, 44, 0.1)
    assert result["volume"] == "0.02"
    assert result["risk_cash"] == "20.88"
    assert result["grants_authority"] is False
    sdk.order_send.assert_not_called()


def test_minimum_lot_is_rejected_not_rounded_up(sdk):
    result = _sizing_quote(sdk, "XAUUSD", 1, "server", "BUY", 2300, 2280, 10, 44, 0.1)
    assert result["reason"] == "MINIMUM_LOT_EXCEEDS_RISK"


def test_unknown_broker_loss_fails_closed(sdk):
    sdk.order_calc_profit.side_effect = None
    sdk.order_calc_profit.return_value = None
    with pytest.raises(ValueError, match="BROKER_LOSS_CALCULATION_UNKNOWN"):
        _sizing_quote(sdk, "XAUUSD", 1, "server", "BUY", 2300, 2290, 25, 44, 0.1)

