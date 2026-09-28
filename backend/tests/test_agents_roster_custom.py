"""Tests for the dynamic roster, custom strategies, and continuous tester."""

from __future__ import annotations

import pytest
from ats.agents.custom import (
    CustomRegistry,
    StrategyValidationError,
    hash_source,
)
from ats.agents.families import DIVERSE_FAMILIES, register_diverse_families
from ats.agents.roster import (
    DEFAULT_FLEET,
    Roster,
    RosterError,
    build_default_roster,
    default_entry,
)
from ats.agents.strategies import STRATEGY_REGISTRY, ensure_diverse_families_loaded

GOOD_SOURCE = """
from ats.agents.strategies import StrategySignal
from ats.agents.features import atr_geometry

def my_breakout(bars, *, tick_size=0.01, **kwargs):
    if len(bars) < 30:
        return None
    closes = [b.close for b in bars]
    if closes[-1] > max(closes[-21:-1]):
        geom = atr_geometry(bars, atr_multiplier=1.5, risk_reward=2.0, tick_size=tick_size)
        return StrategySignal(
            strategy_id="X01_MY_BREAKOUT",
            direction="LONG",
            confidence=0.75,
            regime="CUSTOM",
            rationale="20-bar breakout",
            geometry=geom,
        )
    return None
"""


# ---------------------------------------------------------------------------
# Diverse families
# ---------------------------------------------------------------------------


def test_diverse_families_register():
    register_diverse_families()
    ensure_diverse_families_loaded()
    for name in DIVERSE_FAMILIES:
        assert name in STRATEGY_REGISTRY


def test_diverse_families_are_distinct_from_trend_and_meanrev():
    """The point of the new families is that they are not price-direction bets."""
    assert not ({"donchian", "tsmom", "vwap_trend"} & set(DIVERSE_FAMILIES))
    assert not ({"zscore", "fade_extreme"} & set(DIVERSE_FAMILIES))


# ---------------------------------------------------------------------------
# Roster
# ---------------------------------------------------------------------------


def test_default_roster_has_four_agents():
    r = build_default_roster()
    assert r.size() == 4


def test_default_roster_families_are_unique():
    r = build_default_roster()
    families = [e.family for e in r.entries]
    assert len(set(families)) == len(families)


def test_default_roster_is_diversified():
    r = build_default_roster()
    entries = r.entries
    assert len({e.bar_seconds for e in entries}) >= 2
    assert len({i for e in entries for i in e.instrument_bias}) >= 2


def test_add_agent(tmp_path):
    r = build_default_roster(path=tmp_path / "r.json")
    e = r.add(
        name="Echo",
        family="Seasonality",
        signal_source="session_seasonality",
        horizon="LONG_TERM_SWING",
        bar_seconds=1800.0,
    )
    assert e.name == "Echo"
    assert r.size() == 5
    assert "Echo" in r.names()


def test_add_rejects_duplicate_family(tmp_path):
    r = build_default_roster(path=tmp_path / "r.json")
    with pytest.raises(RosterError, match="already covered"):
        r.add(name="Dup", family="Hurst", signal_source="hurst_regime")


def test_add_rejects_unknown_strategy(tmp_path):
    r = build_default_roster(path=tmp_path / "r.json")
    with pytest.raises(RosterError, match="Unknown signal source"):
        r.add(name="X", family="New", signal_source="nope_not_real")


def test_add_rejects_duplicate_name(tmp_path):
    r = build_default_roster(path=tmp_path / "r.json")
    with pytest.raises(RosterError, match="already exists"):
        r.add(name="Alpha", family="New", signal_source="squeeze")


def test_remove_agent(tmp_path):
    r = build_default_roster(path=tmp_path / "r.json")
    r.remove("Alpha")
    assert r.size() == 3
    assert "Alpha" not in r.names()


def test_remove_unknown_agent(tmp_path):
    r = build_default_roster(path=tmp_path / "r.json")
    with pytest.raises(RosterError, match="not in the roster"):
        r.remove("Ghost")


def test_cannot_remove_last_agent(tmp_path):
    r = Roster([default_entry(DEFAULT_FLEET[0])], path=tmp_path / "r.json")
    with pytest.raises(RosterError, match="last agent"):
        r.remove(DEFAULT_FLEET[0].agent)


def test_assign_strategy(tmp_path):
    r = build_default_roster(path=tmp_path / "r.json")
    e = r.assign_strategy("Alpha", "squeeze")
    assert e.signal_source == "squeeze"


def test_assign_strategy_rejects_unknown(tmp_path):
    r = build_default_roster(path=tmp_path / "r.json")
    with pytest.raises(RosterError, match="Unknown signal source"):
        r.assign_strategy("Alpha", "not_a_strategy")


def test_roster_persists(tmp_path):
    p = tmp_path / "r.json"
    r = build_default_roster(path=p)
    r.add(name="Echo", family="Seasonality", signal_source="session_seasonality")
    assert p.exists()
    reloaded = Roster.load(p)
    assert reloaded.size() == 5
    assert "Echo" in reloaded.names()


def test_reset_to_default_fleet(tmp_path):
    r = build_default_roster(path=tmp_path / "r.json")
    r.add(name="Echo", family="Seasonality", signal_source="session_seasonality")
    r.reset_to_default()
    assert r.size() == 4
    assert "Echo" not in r.names()


# ---------------------------------------------------------------------------
# Custom strategies
# ---------------------------------------------------------------------------


def test_register_custom_strategy():
    reg = CustomRegistry()
    s = reg.register(name="my_breakout", source=GOOD_SOURCE)
    assert s.name == "my_breakout"
    assert s.source_hash
    assert "my_breakout" in STRATEGY_REGISTRY


def test_custom_strategy_runs():
    from ats.agents.features import Bar

    reg = CustomRegistry()
    reg.register(name="my_breakout", source=GOOD_SOURCE)

    bars = []
    for i in range(40):
        c = 100.0 + (i if i >= 35 else 0)
        bars.append(
            Bar(
                timestamp=i * 300.0, open=c, high=c + 1, low=c - 1,
                close=c, volume=1.0, tick_count=5,
            )
        )

    from ats.agents.strategies import evaluate_strategy

    sig = evaluate_strategy("my_breakout", bars)
    assert sig is not None


def test_custom_strategy_rejects_syntax_error():
    reg = CustomRegistry()
    with pytest.raises(StrategyValidationError, match="Syntax error"):
        reg.register(name="bad", source="def bad(:\n  pass")


def test_custom_strategy_rejects_open():
    reg = CustomRegistry()
    with pytest.raises(StrategyValidationError, match="not permitted"):
        reg.register(name="bad", source="def bad(bars):\n    return open('/etc/passwd')")


def test_custom_strategy_rejects_eval():
    reg = CustomRegistry()
    with pytest.raises(StrategyValidationError, match="not permitted"):
        reg.register(name="bad", source="def bad(bars):\n    return eval('1+1')")


def test_custom_strategy_rejects_dunder():
    reg = CustomRegistry()
    with pytest.raises(StrategyValidationError, match="dunder"):
        reg.register(name="bad", source="def bad(bars):\n    return bars.__class__")


def test_custom_strategy_requires_matching_function_name():
    reg = CustomRegistry()
    with pytest.raises(StrategyValidationError, match="must define"):
        reg.register(name="expected_name", source="def something_else(bars):\n    return None")


def test_custom_registry_remove():
    reg = CustomRegistry()
    reg.register(name="tmp_strategy", source=GOOD_SOURCE.replace("my_breakout", "tmp_strategy"))
    assert reg.remove("tmp_strategy")
    assert "tmp_strategy" not in STRATEGY_REGISTRY


def test_source_hash_is_stable():
    assert hash_source("abc") == hash_source("abc")
    assert hash_source("abc") != hash_source("abd")
