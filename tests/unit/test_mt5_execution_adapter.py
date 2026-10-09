from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from ats.execution.metatrader_adapter import MT5ExecutionAdapter

from tests.unit.test_external_authority import inputs


class SDK:
    ORDER_FILLING_FOK = 0
    ORDER_FILLING_IOC = 1
    SYMBOL_FILLING_FOK = 1
    SYMBOL_FILLING_IOC = 2
    ACCOUNT_TRADE_MODE_DEMO = 0
    ACCOUNT_TRADE_MODE_REAL = 2
    TRADE_ACTION_DEAL = 1
    ORDER_TYPE_BUY = 0
    ORDER_TYPE_SELL = 1
    ORDER_TIME_GTC = 0
    TRADE_RETCODE_DONE = 10009
    TRADE_RETCODE_DONE_PARTIAL = 10010
    TRADE_RETCODE_PLACED = 10008
    TRADE_RETCODE_REJECT = 10006
    TRADE_RETCODE_INVALID = 10013
    TRADE_RETCODE_INVALID_VOLUME = 10014
    TRADE_RETCODE_INVALID_STOPS = 10016
    TRADE_RETCODE_NO_MONEY = 10019
    TRADE_RETCODE_TRADE_DISABLED = 10017

    def __init__(self):
        self.intent, _, _, self.now = inputs()
        self.login = 7
        self.enabled = True
        self.tick_time = self.now.timestamp() * 1000
        self.retcode = self.TRADE_RETCODE_DONE
        self.calls = []
        self.check = 0
        self.ack = True

    def account_info(self):
        return SimpleNamespace(
            login=self.login,
            server="TEST",
            trade_allowed=self.enabled,
            trade_expert=True,
            margin_free=1000,
            trade_mode=self.ACCOUNT_TRADE_MODE_DEMO,
        )

    def terminal_info(self):
        return SimpleNamespace(
            connected=True,
            trade_allowed=self.enabled,
            tradeapi_disabled=False,
        )

    def symbol_info_tick(self, symbol):
        return SimpleNamespace(bid=1999.99, ask=2000, time_msc=self.tick_time)

    def symbol_info(self, symbol):
        return SimpleNamespace(
            point=0.01,
            trade_tick_size=0.01,
            volume_min=0.01,
            volume_max=10,
            volume_step=0.01,
            trade_stops_level=0,
            filling_mode=3,
        )

    def order_calc_profit(self, order_type, symbol, volume, entry, sl):
        return -100

    def order_calc_margin(self, order_type, symbol, volume, entry):
        return 50

    def order_check(self, request):
        return SimpleNamespace(retcode=self.check)

    def order_send(self, request):
        self.calls.append(request)
        return (
            SimpleNamespace(retcode=self.retcode, order=42, deal=84, price=2000, volume=0.1)
            if self.ack
            else None
        )


def adapter(sdk):
    return MT5ExecutionAdapter(
        sdk, expected_login=7, expected_server="TEST", broker_symbol="XAUUSDm", filling_mode=0
    )


def test_real_request_mapping_with_fake_sdk():
    sdk = SDK()
    assert adapter(sdk).submit(sdk.intent)["state"] == "ACCEPTED"
    request = sdk.calls[0]
    assert request["symbol"] == "XAUUSDm"
    assert request["sl"] == 1990 and request["tp"] == 2020
    assert request["type"] == sdk.ORDER_TYPE_BUY
    assert "password" not in request and "login" not in request


@pytest.mark.parametrize(
    "field,value", [("login", 99), ("enabled", False), ("check", 1), ("tick_time", 0)]
)
def test_adapter_rechecks_identity_clock_and_permission(field, value):
    sdk = SDK()
    setattr(sdk, field, value)
    assert adapter(sdk).submit(sdk.intent)["state"] == "REJECTED"
    assert not sdk.calls


@pytest.mark.parametrize(
    "code,state", [(10010, "ACCEPTED"), (10006, "REJECTED"), (10012, "UNKNOWN")]
)
def test_partial_rejection_timeout(code, state):
    sdk = SDK()
    sdk.retcode = code
    assert adapter(sdk).submit(sdk.intent)["state"] == state
    assert len(sdk.calls) == 1


def test_missing_ack_never_retried():
    sdk = SDK()
    sdk.ack = False
    assert adapter(sdk).submit(sdk.intent)["state"] == "UNKNOWN"
    assert len(sdk.calls) == 1


@pytest.mark.parametrize("missing", ["trade_expert", "tradeapi_disabled"])
def test_unknown_native_execution_permissions_are_rejected(missing):
    sdk = SDK()
    if missing == "trade_expert":
        original = sdk.account_info()
        delattr(original, missing)
        sdk.account_info = lambda: original
    else:
        original = sdk.terminal_info()
        delattr(original, missing)
        sdk.terminal_info = lambda: original
    assert adapter(sdk).submit(sdk.intent)["state"] == "REJECTED"
    assert not sdk.calls


@pytest.mark.parametrize("profit", [None, float("nan"), -101, 0, 100])
def test_unknown_or_excess_stop_loss_never_reaches_broker(profit):
    sdk = SDK()
    sdk.order_calc_profit = lambda *_: profit
    assert adapter(sdk).submit(sdk.intent)["state"] == "REJECTED"
    assert not sdk.calls


@pytest.mark.parametrize("margin", [None, float("nan"), 51, 0, -1])
def test_unknown_or_excess_margin_never_reaches_broker(margin):
    sdk = SDK()
    sdk.order_calc_margin = lambda *_: margin
    assert adapter(sdk).submit(sdk.intent)["state"] == "REJECTED"
    assert not sdk.calls


@pytest.mark.parametrize(
    "field,value",
    [
        ("trade_tick_size", 0.03),
        ("volume_step", 0.03),
        ("filling_mode", 2),
        ("trade_stops_level", 1001),
        ("point", float("nan")),
    ],
)
def test_broker_metadata_grid_stop_and_filling_constraints(field, value):
    sdk = SDK()
    info = sdk.symbol_info("XAUUSDm")
    setattr(info, field, value)
    sdk.symbol_info = lambda _: info
    assert adapter(sdk).submit(sdk.intent)["state"] == "REJECTED"
    assert not sdk.calls


def test_clock_conversion_requires_explicit_injected_verified_normalizer():
    sdk = SDK()
    sdk.tick_time += 3 * 3600 * 1000
    assert adapter(sdk).submit(sdk.intent)["state"] == "REJECTED"
    normalized = MT5ExecutionAdapter(
        sdk,
        expected_login=7,
        expected_server="TEST",
        broker_symbol="XAUUSDm",
        filling_mode=0,
        normalize_tick=lambda stamp, server, now: datetime.fromtimestamp(stamp / 1000, UTC)
        - timedelta(hours=3),
    )
    assert normalized.submit(sdk.intent)["state"] == "ACCEPTED"
    assert len(sdk.calls) == 1


def test_mode_change_cannot_reuse_default_demo_adapter():
    sdk = SDK()
    account = sdk.account_info()
    account.trade_mode = sdk.ACCOUNT_TRADE_MODE_REAL
    sdk.account_info = lambda: account
    assert adapter(sdk).submit(sdk.intent)["reason"] == "ACCOUNT_MODE_CHANGED"
    assert not sdk.calls
