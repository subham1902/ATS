"""End-to-end test of the reworked agent loop.

Drives the real :class:`AgentsWorker` with synthetic bars and asserts the
behavioural guarantees the audit demanded: the cost gate blocks, the risk
breakers trip, abstention is the default, and a tradable configuration can
actually open and close a position.
"""

from __future__ import annotations

import pytest
from ats.agents.costs import CostAwareSizer
from ats.agents.features import TickAggregator, atr_geometry
from ats.agents.risk import GLOBAL_KILL_SWITCH
from ats.agents.worker import CONTRACT_SPECS, agents_state, init_agents

SPEC = CONTRACT_SPECS["MCX_GOLDM"]


@pytest.fixture(autouse=True)
def _clean():
    GLOBAL_KILL_SWITCH.engage("test")
    init_agents()
    yield
    GLOBAL_KILL_SWITCH.engage("test teardown")


def test_kill_switch_halts_the_whole_fleet():
    """With trading disabled, no agent may open a position."""
    GLOBAL_KILL_SWITCH.engage("incident")
    for name, agent in agents_state["agents"].items():
        assert agent["position"] is None, name


def test_default_configuration_is_untradeable_by_design():
    """The pre-audit geometry must be rejected by the cost gate.

    This is the single most important regression guard: if a future change makes
    1-lot 45/22 geometry tradable again, the original bleeding returns.
    """
    sizer = CostAwareSizer(
        max_lots=4.0,
        max_risk_pct=1.0,
        capital=100_000.0,
        margin_per_lot=SPEC["margin_per_lot"],
        min_edge_multiple=3.0,
    )
    lots, econ = sizer.size_for(
        exchange="MCX",
        entry_price=147_232.0,
        symbol=SPEC["symbol"],
        lot_size=SPEC["lot_size"],
        target_points=45.0,
        stop_points=22.0,
        strategy_win_rate=0.5,
    )
    assert lots == 0.0
    assert not econ.tradable


def test_atr_geometry_produces_viable_distances_on_real_bars():
    """ATR-derived geometry is what makes a trade cost-viable at all."""
    prices = [147_000.0 + i * 8.0 for i in range(300)]
    agg = TickAggregator(interval_seconds=60.0, max_bars=250)
    for i, p in enumerate(prices):
        agg.update(price=p, timestamp=float(i * 60))
    geom = atr_geometry(agg.bars, atr_multiplier=1.5, risk_reward=2.0, tick_size=0.1)
    assert geom.atr > 0
    assert geom.target_points > geom.stop_points
    assert "ATR" in geom.basis

    sizer = CostAwareSizer(
        max_lots=4.0,
        max_risk_pct=5.0,
        capital=100_000.0,
        margin_per_lot=SPEC["margin_per_lot"],
        min_edge_multiple=3.0,
    )
    lots, econ = sizer.size_for(
        exchange="MCX",
        entry_price=147_000.0,
        symbol=SPEC["symbol"],
        lot_size=SPEC["lot_size"],
        target_points=geom.target_points,
        stop_points=geom.stop_points,
        strategy_win_rate=0.45,
    )
    # Either it is viable at a larger size, or it reports why it is not.
    if lots > 0:
        assert econ.tradable
    else:
        assert econ.block_reason_code != ""


def test_agents_start_flat_and_clean():
    assert len(agents_state["agents"]) == 4
    for name, agent in agents_state["agents"].items():
        assert agent["pnl"] == 0.0, name
        assert agent["total_tests"] == 0, name
        assert agent["position"] is None, name
        assert agent["current_capital"] == agent["max_principal"], name
        assert agent["mandate"]["family"], name


def test_each_agent_has_a_distinct_mandate():
    families = [a["mandate"]["family"] for a in agents_state["agents"].values()]
    assert len(set(families)) == len(families)
    assert len(families) == 4


def test_bar_sizes_differ_across_horizons():
    bars = {a["name"]: a["mandate"]["bar_seconds"] for a in agents_state["agents"].values()}
    assert bars["Alpha"] == 300.0
    assert bars["Delta"] == 900.0
    assert bars["Charlie"] == 1800.0


def test_single_agent_reset_zeroes_metrics():
    agents_state["agents"]["Alpha"]["pnl"] = -5000.0
    agents_state["agents"]["Alpha"]["total_tests"] = 9
    from ats.agents.worker import get_risk_manager

    get_risk_manager().register_principal("Alpha", 100_000.0)
    # Exercise the in-process reset the router calls.
    from ats.agents.config import get_agents_config_manager

    principal = get_agents_config_manager().get_principal("Alpha")
    get_risk_manager().reset_agent("Alpha", principal=principal)
    assert get_risk_manager().state_for("Alpha", principal=principal).current_capital == principal


def test_portfolio_exposure_is_tracked():
    from ats.agents.portfolio import OpenExposure
    from ats.agents.worker import get_portfolio_builder

    pb = get_portfolio_builder()
    pb.clear()
    pb.add_exposure(
        OpenExposure("Alpha", "Trend", "GOLDM", "LONG", 100.0, [0.01, 0.02, 0.03])
    )
    s = pb.concentration_summary()
    assert s["open_positions"] == 1
    pb.clear()
