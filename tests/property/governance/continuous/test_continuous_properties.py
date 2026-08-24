"""The continuous governor cannot model authority-bearing output."""

from __future__ import annotations

from ats.governance.continuous import MarketEventDispatch


def test_dispatch_result_has_no_order_or_authorization_field() -> None:
    fields = set(MarketEventDispatch.model_fields)
    forbidden = {"order", "token", "risk_decision", "reservation", "broker"}
    assert not any(any(word in field for word in forbidden) for field in fields)
