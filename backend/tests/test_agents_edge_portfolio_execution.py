"""Tests for statistical edge evaluation, portfolio construction, and execution."""

from __future__ import annotations

from ats.agents.edge import (
    StrategyEdgeRegistry,
    probability_win_rate_exceeds,
)
from ats.agents.execution import ExecutionConfig, ExecutionModel
from ats.agents.portfolio import (
    MANDATES,
    OpenExposure,
    PortfolioBuilder,
    allocate_capital,
    mandate_for,
    validate_mandates,
)

# ---------------------------------------------------------------------------
# Edge registry
# ---------------------------------------------------------------------------


def test_no_verdict_before_minimum_sample():
    r = StrategyEdgeRegistry()
    for _ in range(5):
        r.record_trade("S01", net_pnl=-100.0, gross_pnl=-100.0, charges=0.0)
    v = r.evaluate("S01", required_win_rate=0.4, net_if_win=100.0, net_if_loss=-100.0)
    assert v.status == "INSUFFICIENT_EVIDENCE"
    assert not v.sample_sufficient


def test_strong_strategy_graduates():
    r = StrategyEdgeRegistry()
    for _ in range(120):
        r.record_trade("S01", net_pnl=200.0, gross_pnl=200.0, charges=0.0)
    v = r.evaluate("S01", required_win_rate=0.4, net_if_win=200.0, net_if_loss=-100.0)
    assert v.status == "GRADUATED"
    assert v.recommended_lot_multiplier > 1.0


def test_losing_strategy_is_negative_expectancy():
    r = StrategyEdgeRegistry()
    for _ in range(120):
        r.record_trade("S01", net_pnl=-100.0, gross_pnl=-100.0, charges=0.0)
    v = r.evaluate("S01", required_win_rate=0.4, net_if_win=200.0, net_if_loss=-100.0)
    assert v.status == "NEGATIVE_EXPECTANCY"


def test_posterior_shrinks_toward_prior():
    r = StrategyEdgeRegistry()
    for _ in range(2):
        r.record_trade("S01", net_pnl=500.0, gross_pnl=500.0, charges=0.0)
    v = r.evaluate("S01", required_win_rate=0.5, net_if_win=1.0, net_if_loss=-1.0)
    # Two wins should not produce a 100% win-rate belief.
    assert 0.35 < v.posterior_win_rate < 0.75


def test_should_not_retire_on_two_losses():
    r = StrategyEdgeRegistry()
    r.record_trade("S01", net_pnl=-100.0, gross_pnl=-100.0, charges=50.0)
    r.record_trade("S01", net_pnl=-100.0, gross_pnl=-100.0, charges=50.0)
    retire, _ = r.should_retire("S01")
    assert not retire


def test_probability_monotonic_in_wins():
    low = probability_win_rate_exceeds(1, 50, 0.4)
    high = probability_win_rate_exceeds(40, 20, 0.4)
    assert high > low


# ---------------------------------------------------------------------------
# Portfolio
# ---------------------------------------------------------------------------


def test_mandates_are_healthy():
    assert validate_mandates() == []


def test_every_agent_has_a_distinct_family():
    families = [m.family for m in MANDATES]
    assert len(set(families)) == len(families)


def test_mandate_lookup():
    assert mandate_for("Alpha") is not None
    assert mandate_for("Nonexistent") is None


def test_duplicate_family_exposure_blocked():
    p = PortfolioBuilder(max_pair_correlation=0.6)
    p.add_exposure(
        OpenExposure("Alpha", "Trend", "GOLDM", "LONG", 100.0, [0.01, 0.02, 0.01])
    )
    check = p.check(
        agent="Golf",
        family="Trend",  # deliberately duplicate
        instrument="GOLDM",
        direction="LONG",
        proposed_returns=[0.01, 0.02, 0.01],
    )
    assert not check.allowed
    assert "family" in check.reason


def test_correlated_exposure_blocked():
    p = PortfolioBuilder(max_pair_correlation=0.6)
    rets = [0.01, 0.02, -0.01, 0.03, 0.005, -0.02, 0.01]
    p.add_exposure(OpenExposure("Alpha", "Trend", "GOLDM", "LONG", 100.0, list(rets)))
    check = p.check(
        agent="Charlie",
        family="MeanReversion",
        instrument="GOLDM",
        direction="LONG",
        proposed_returns=list(rets),
    )
    assert not check.allowed


def test_uncorrelated_exposure_allowed():
    p = PortfolioBuilder(max_pair_correlation=0.6)
    peer = [0.01, -0.02, 0.03, -0.01, 0.025, -0.015, 0.005, 0.018]
    p.add_exposure(OpenExposure("Alpha", "Trend", "GOLDM", "LONG", 100.0, list(peer)))
    proposed = [-0.0127, -0.007, -0.0163, -0.0173, -0.0217, -0.0063, -0.0056, 0.0247]
    check = p.check(
        agent="Charlie",
        family="MeanReversion",
        instrument="GOLDM",
        direction="LONG",
        proposed_returns=proposed,
    )
    assert check.allowed, f"rho={check.worst_correlation}"
    assert abs(check.worst_correlation) < 0.1


def test_perfect_anticorrelation_also_rejected():
    """Same-instrument anticorrelation still concentrates risk, so it is blocked."""
    p = PortfolioBuilder(max_pair_correlation=0.6)
    rets = [0.01, -0.02, 0.03, -0.01, 0.02]
    p.add_exposure(OpenExposure("Alpha", "Trend", "GOLDM", "LONG", 100.0, list(rets)))
    check = p.check(
        agent="Charlie",
        family="MeanReversion",
        instrument="GOLDM",
        direction="LONG",
        proposed_returns=[-r for r in rets],
    )
    assert not check.allowed


def test_concentration_summary_flags_duplicates():
    p = PortfolioBuilder(max_pair_correlation=0.9)
    p.add_exposure(OpenExposure("Alpha", "Trend", "GOLDM", "LONG", 100.0, [0.01]))
    p.add_exposure(OpenExposure("Golf", "Trend", "GOLDM", "LONG", 100.0, [0.01]))
    s = p.concentration_summary()
    assert s["duplicate_family_exposure"]


def test_allocation_without_edge_uses_principal():
    a = allocate_capital({"Alpha": 100_000.0, "Bravo": 200_000.0})
    assert a.method == "EQUAL_TO_PRINCIPAL"
    assert a.per_agent_capital["Bravo"] == 200_000.0


def test_allocation_tilts_to_edge_within_bounds():
    a = allocate_capital(
        {"Alpha": 100_000.0, "Bravo": 100_000.0},
        edge_scores={"Alpha": 10.0, "Bravo": 0.0},
    )
    assert a.method == "EDGE_TILTED"
    assert a.per_agent_capital["Alpha"] > a.per_agent_capital["Bravo"]
    assert a.per_agent_capital["Alpha"] <= 100_000.0


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------


#: Realistic MCX gold price. Slippage is a fraction of price, so tests use a
#: realistic notional rather than a toy price where rounding would hide it.
GOLD_PRICE = 147_232.0


def test_entry_slippage_is_adverse():
    m = ExecutionModel(ExecutionConfig(reject_probability=0.0))
    long_fill = m.apply_entry(price=GOLD_PRICE, direction="LONG", order_id="a")
    short_fill = m.apply_entry(price=GOLD_PRICE, direction="SHORT", order_id="b")
    assert long_fill.price > GOLD_PRICE
    assert short_fill.price < GOLD_PRICE


def test_stop_exit_slips_more_than_target_exit():
    m = ExecutionModel(ExecutionConfig(reject_probability=0.0))
    stop = m.apply_exit(price=GOLD_PRICE, direction="LONG", order_id="s", reason="STOP_LOSS")
    target = m.apply_exit(
        price=GOLD_PRICE, direction="LONG", order_id="t", reason="PROFIT_TARGET"
    )
    assert stop.price < GOLD_PRICE
    assert target.price < GOLD_PRICE
    assert stop.slippage_points > 0.0


def test_execution_is_deterministic():
    a = ExecutionModel(ExecutionConfig(reject_probability=0.0))
    b = ExecutionModel(ExecutionConfig(reject_probability=0.0))
    fa = a.apply_entry(price=GOLD_PRICE, direction="LONG", order_id="same")
    fb = b.apply_entry(price=GOLD_PRICE, direction="LONG", order_id="same")
    assert fa.price == fb.price


def test_rejection_can_occur():
    m = ExecutionModel(ExecutionConfig(reject_probability=1.0))
    f = m.apply_entry(price=GOLD_PRICE, direction="LONG", order_id="x")
    assert f.rejected
    assert m.stats["rejections"] == 1


def test_latency_within_bounds():
    cfg = ExecutionConfig()
    m = ExecutionModel(cfg)
    for i in range(20):
        f = m.apply_entry(price=GOLD_PRICE, direction="LONG", order_id=f"o{i}")
        assert cfg.min_latency_seconds <= f.latency_seconds <= cfg.max_latency_seconds
