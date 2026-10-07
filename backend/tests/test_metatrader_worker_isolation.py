"""Real spawned workers with a synthetic SDK; never connect a trading account."""

from pathlib import Path

import pytest
from ats.market.metatrader.account_session import Mt5AccountSession

FAKE_SDK = """
from collections import namedtuple
from pathlib import Path
from time import time
ACCOUNT_TRADE_MODE_DEMO = 0
ACCOUNT_TRADE_MODE_REAL = 2
settings = {}
def initialize(**options):
    settings.update(options)
    return not options['path'].endswith('missing.exe')
def terminal_info():
    return namedtuple('Terminal', 'connected data_path')(True, settings['path'] + '/profile')
def account_info():
    login = settings['login']
    if Path(settings['path'] + '.switch').exists():
        login += 1
    return namedtuple('Account',
        'login server trade_mode balance equity margin margin_free currency')(
        login, settings['server'], 0, 10000, 10000, 0, 10000, 'USD')
def positions_get(**options):
    return ()
def orders_get(**options):
    return ()
def symbol_select(symbol, enable):
    return symbol == 'GOLD'
def symbol_info(symbol):
    return namedtuple('Metadata',
        'name digits point trade_tick_size trade_contract_size volume_min '
        'volume_max volume_step trade_mode currency_base currency_profit')(
        symbol, 2, .01, .01, 100, .01, 100, .01, 4, 'XAU', 'USD')
def symbol_info_tick(symbol):
    return namedtuple('Tick', 'time_msc bid ask last volume volume_real flags')(
        int(time()*1000), 2300, 2300.2, 0, 0, 0, 6)
def shutdown():
    settings.clear()
"""


def settings(path: Path, login: int):
    return {
        "path": str(path),
        "login": login,
        "password": "fixture",
        "server": "TestServer",
        "symbol": "GOLD",
        "timeout": 1000,
    }


def test_spawned_accounts_are_isolated_and_detect_terminal_account_switch(tmp_path, monkeypatch):
    (tmp_path / "MetaTrader5.py").write_text(FAKE_SDK, encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    first = Mt5AccountSession(settings(tmp_path / "one.exe", 1))
    second = Mt5AccountSession(settings(tmp_path / "two.exe", 2))
    try:
        assert first.initialize()
        assert second.initialize()
        assert first._process.pid != second._process.pid
        assert (
            first.snapshot("GOLD")["terminal_profile"]
            != second.snapshot("GOLD")["terminal_profile"]
        )
        assert first.latest_tick("GOLD")["bid"] == 2300
        (tmp_path / "one.exe.switch").touch()
        with pytest.raises(ValueError, match="ACCOUNT_SESSION_OPERATION_FAILED"):
            first.latest_tick("GOLD")
        assert second.latest_tick("GOLD")["bid"] == 2300
    finally:
        first.shutdown()
        second.shutdown()


def test_missing_terminal_fails_without_exposing_sdk_error(tmp_path, monkeypatch):
    (tmp_path / "MetaTrader5.py").write_text(FAKE_SDK, encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    session = Mt5AccountSession(settings(tmp_path / "missing.exe", 1))
    try:
        with pytest.raises(ValueError, match="ACCOUNT_SESSION_OPERATION_FAILED"):
            session.initialize()
    finally:
        session.shutdown()
