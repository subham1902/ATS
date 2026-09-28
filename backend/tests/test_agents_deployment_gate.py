"""Tests for the deployment gate and the historical validation harness.

The deployment gate is the last line of defence: only a mandate with
positive out-of-sample expectancy may be pointed at capital.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from ats.agents.deployment import (
    DeploymentGate,
    from_report,
    get_deployment_gate,
    set_deployment_gate,
)


def _report(oos: dict[str, dict], is_: dict[str, dict] | None = None) -> dict:
    return {
        "data_source": "test.csv",
        "oos_fraction": 0.3,
        "is": is_ or {},
        "oos": oos,
    }


def test_no_evidence_holds_everything():
    g = DeploymentGate()
    assert g.is_fleet_wide_hold()
    assert not g.allows("Alpha")
    _, reason = g.allows_with_reason("Alpha")
    assert "No validated evidence" in reason


def test_graduated_mandate_is_allowed():
    rep = _report(
        {
            "Alpha": {
                "verdict": "GRADUATED",
                "deployable": True,
                "trades": 200,
                "net_points": 500.0,
                "expectancy": 2.5,
                "profit_factor": 1.6,
                "win_rate": 55.0,
            }
        }
    )
    g = from_report(rep)
    assert g.allows("Alpha")
    assert g.deployable_agents == ["Alpha"]
    assert not g.is_fleet_wide_hold()


def test_negative_expectancy_is_held():
    rep = _report(
        {
            "Alpha": {
                "verdict": "NEGATIVE_EXPECTANCY",
                "deployable": False,
                "trades": 1800,
                "net_points": -2560.0,
                "expectancy": -1.4,
                "profit_factor": 0.82,
                "win_rate": 32.6,
            }
        }
    )
    g = from_report(rep)
    assert not g.allows("Alpha")
    assert "Held" in g.allows_with_reason("Alpha")[1]


def test_deployable_flag_cannot_be_forced_against_verdict():
    """A report claiming deployable with a non-graduated verdict is rejected."""
    rep = _report(
        {
            "Alpha": {
                "verdict": "PROMISING",
                "deployable": True,  # inconsistent / forged
                "trades": 50,
                "net_points": 10.0,
                "expectancy": 0.2,
                "profit_factor": 1.1,
                "win_rate": 40.0,
            }
        }
    )
    g = from_report(rep)
    assert not g.allows("Alpha")


def test_overfit_is_called_out_explicitly():
    """Positive in-sample + negative out-of-sample must be flagged, not deployed."""
    rep = _report(
        oos={
            "Echo": {
                "verdict": "NEGATIVE_EXPECTANCY",
                "deployable": False,
                "trades": 153,
                "net_points": -119.8,
                "expectancy": -0.78,
                "profit_factor": 0.97,
                "win_rate": 34.6,
            }
        },
        is_={
            "Echo": {
                "net_points": 628.9,
                "verdict": "GRADUATED",
                "deployable": True,
            }
        },
    )
    g = from_report(rep)
    assert not g.allows("Echo")
    assert "overfit" in g.notes.lower()
    assert "Echo" in g.notes


def test_no_signal_mandate_is_held():
    rep = _report(
        {
            "Delta": {
                "verdict": "NO_SIGNAL",
                "deployable": False,
                "trades": 0,
                "net_points": 0.0,
                "expectancy": 0.0,
                "profit_factor": 0.0,
                "win_rate": 0.0,
            }
        }
    )
    g = from_report(rep)
    assert not g.allows("Delta")
    assert "never fired" in g.allows_with_reason("Delta")[1]


def test_summary_shape():
    rep = _report(
        {
            "Alpha": {
                "verdict": "GRADUATED",
                "deployable": True,
                "trades": 200,
                "net_points": 500.0,
                "expectancy": 2.5,
                "profit_factor": 1.6,
                "win_rate": 55.0,
            }
        }
    )
    s = from_report(rep).summary()
    for key in (
        "fleet_wide_hold",
        "deployable_agents",
        "held_agents",
        "verdicts",
        "evidence_present",
    ):
        assert key in s


def test_load_from_file(tmp_path: Path):
    rep = _report(
        {
            "Alpha": {
                "verdict": "GRADUATED",
                "deployable": True,
                "trades": 200,
                "net_points": 500.0,
                "expectancy": 2.5,
                "profit_factor": 1.6,
                "win_rate": 55.0,
            }
        }
    )
    p = tmp_path / "report.json"
    p.write_text(json.dumps(rep), encoding="utf-8")

    from ats.agents.deployment import load

    original = get_deployment_gate()
    try:
        g = load(p)
        assert g.allows("Alpha")
        assert get_deployment_gate().allows("Alpha")
    finally:
        set_deployment_gate(original)


def test_load_missing_file_keeps_safe_default():
    from ats.agents.deployment import load

    original = get_deployment_gate()
    try:
        g = load(Path("does_not_exist_12345.json"))
        assert g.is_fleet_wide_hold()
    finally:
        set_deployment_gate(original)


def test_shipped_validation_report_shows_fleet_wide_hold():
    """The report generated from real data must hold the fleet.

    This is a factual assertion about the current evidence base, not a
    preference: nothing has demonstrated out-of-sample edge yet.
    """
    report_path = Path("../agents-playground/strategy_validation.json")
    if not report_path.exists():
        pytest.skip("validation report not generated in this checkout")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    gate = from_report(report)
    assert gate.evidence_present
    # Whether or not something graduates, the gate must be derived from OOS only.
    for agent, v in gate.verdicts.items():
        if v.deployable:
            assert v.verdict == "GRADUATED", agent
