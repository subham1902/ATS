"""Observe permissions without implying ATS authority or exposing credentials."""

from types import SimpleNamespace

import pytest
from ats.market.metatrader.account_session import _safe_snapshot


def sdk(**permissions):
    terminal = SimpleNamespace(connected=True, data_path="test-profile", **permissions)
    account = SimpleNamespace(
        login=123,
        server="Test",
        trade_mode=0,
        balance=1000,
        equity=1000,
        margin=0,
        margin_free=1000,
        currency="USD",
        password="never-export",
    )
    return SimpleNamespace(
        terminal_info=lambda: terminal,
        account_info=lambda: account,
        positions_get=lambda **kwargs: (),
        orders_get=lambda **kwargs: (),
        ACCOUNT_TRADE_MODE_DEMO=0,
        ACCOUNT_TRADE_MODE_REAL=2,
    )


@pytest.mark.parametrize("allowed", [True, False])
def test_permissions_are_observed_not_authority(allowed):
    result = _safe_snapshot(
        sdk(trade_allowed=allowed, tradeapi_disabled=False), "XAUUSD", 123, "Test"
    )
    assert result["terminal_algo_trading_allowed"] is allowed
    assert result["terminal_python_trading_disabled"] is False
    assert result["account_expert_trading_allowed"] is None
    assert "password" not in result and "login" not in result
    assert "execution_enabled" not in result


def test_missing_permissions_remain_unknown():
    result = _safe_snapshot(sdk(), "XAUUSD", 123, "Test")
    assert result["terminal_algo_trading_allowed"] is None
    assert result["terminal_python_trading_disabled"] is None
