"""Contract scan for the absence of authority-bearing session fields."""

from __future__ import annotations

from ats.intelligence.advisory import AdvisoryProposal, PositionAdvisoryContext


def test_advisory_models_do_not_represent_financial_authority() -> None:
    forbidden = {"order", "token", "nonce", "budget", "risk_decision", "broker"}
    fields = {*PositionAdvisoryContext.model_fields, *AdvisoryProposal.model_fields}
    assert not any(any(word in field for word in forbidden) for field in fields)
