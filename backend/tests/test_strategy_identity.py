"""Strategy identity: full IDs are the only identity; prefixes never alias."""

import re
from pathlib import Path

import pytest
from ats.strategies.identity import AmbiguousStrategyId, resolve_strategy_id

COLLIDING = ("S02_TSMOM", "S02_MICRO_TICK", "S03_DONCHIAN_ATR", "S03_GAP_FILL")


def _agent_strategy_ids() -> list[str]:
    import ats.strategies.definitions as mod

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
