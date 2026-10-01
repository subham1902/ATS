"""Strategy identity: full IDs are the only identity; prefixes never alias."""

import re
from pathlib import Path

import pytest
from ats.console.strategy_registry_service import StrategyRegistryService
from ats.strategies.identity import AmbiguousStrategyId, resolve_strategy_id

COLLIDING = ("S02_TSMOM", "S02_MICRO_TICK", "S03_DONCHIAN_ATR", "S03_GAP_FILL")


def _agent_strategy_ids() -> list[str]:
    import ats.agents.strategies as mod

    return re.findall(r'sid = "([A-Z0-9_]+)"', Path(mod.__file__).read_text(encoding="utf-8"))


def test_full_ids_are_unique_and_collisions_are_prefix_only():
    ids = _agent_strategy_ids()
    assert len(ids) == len(set(ids))
    assert set(COLLIDING) <= set(ids)
    prefixes = [i.split("_")[0] for i in COLLIDING]
    assert len(set(prefixes)) == 2  # S02 and S03 are each shared; the full ids are not


def test_exact_ids_round_trip_and_unknown_is_none():
    known = _agent_strategy_ids()
    for sid in COLLIDING:
        assert resolve_strategy_id(sid, known) == sid
    assert resolve_strategy_id("S02_NOPE", known) is None


def test_bare_prefix_is_ambiguous_and_fails_closed():
    known = _agent_strategy_ids()
    with pytest.raises(AmbiguousStrategyId):
        resolve_strategy_id("S02", known)
    with pytest.raises(AmbiguousStrategyId):
        resolve_strategy_id("S03", known)


def test_explicit_alias_is_the_only_short_form_allowed():
    known = ["S02_TSMOM", "S02_MICRO_TICK"]
    assert resolve_strategy_id("S02", known, aliases={"S02": "S02_TSMOM"}) == "S02_TSMOM"
    assert resolve_strategy_id("S02", known, aliases={"S02": "GONE"}) is None


@pytest.fixture()
def registry():
    svc = StrategyRegistryService()
    svc._ensure_loaded()
    return svc


def _live(svc, sid, pnl, trades):
    svc.update_live_strategy_performance(
        strategy_id=sid, net_pnl=pnl, win_rate=0.5, profit_factor=1.2, trades_count=trades
    )


def test_live_performance_does_not_leak_between_colliding_ids_or_into_registry_prefix(registry):
    before = registry._entries["S02"].total_trades, registry._entries["S02"].total_net_pnl
    _live(registry, "S02_TSMOM", 111.0, 7)
    _live(registry, "S02_MICRO_TICK", -222.0, 9)
    a, b = registry._entries["S02_TSMOM"], registry._entries["S02_MICRO_TICK"]
    assert a is not b
    assert (a.total_trades, float(a.total_net_pnl)) == (7, 111.0)
    assert (b.total_trades, float(b.total_net_pnl)) == (9, -222.0)
    # The registry's own bare "S02" (a different STRAT-04 id) is untouched.
    assert (registry._entries["S02"].total_trades, registry._entries["S02"].total_net_pnl) == before
    for rec in registry._entries["S02"].performance_records:
        assert not rec.run_id.startswith("live-forward-S02_")


def test_s03_ids_are_isolated_too(registry):
    _live(registry, "S03_DONCHIAN_ATR", 5.0, 1)
    _live(registry, "S03_GAP_FILL", 6.0, 2)
    assert registry._entries["S03_DONCHIAN_ATR"].total_trades == 1
    assert registry._entries["S03_GAP_FILL"].total_trades == 2


def test_score_dict_is_keyed_by_full_id_only(registry):
    _live(registry, "S02_TSMOM", 1.0, 1)
    _live(registry, "S02_MICRO_TICK", 2.0, 1)
    scores = registry.get_strategy_scores_dict()
    assert "S02_TSMOM" in scores and "S02_MICRO_TICK" in scores
    assert scores["S02_TSMOM"] is not scores["S02_MICRO_TICK"]
    # Bare "S02" may exist only as the registry's own entry, never as an alias
    # whose score came from one of the two lab strategies.
    if "S02" in scores:
        assert scores["S02"] is not scores["S02_TSMOM"]
        assert scores["S02"] is not scores["S02_MICRO_TICK"]


def test_no_service_derives_identity_from_a_name_prefix():
    root = Path(__file__).resolve().parents[1] / "src" / "ats"
    for rel in ("console/strategy_registry_service.py", "strategies/lab_service.py"):
        text = (root / rel).read_text(encoding="utf-8")
        assert 'split("_")[0]' not in text, rel
