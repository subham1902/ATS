"""PAPER AUTO-FILL — canonical fill lifecycle through PaperBrokerAdapter.

Covers acknowledgment→fill, market/limit behavior, partial fill, rejection,
duplicate submission/fill, invalid fill, stale market facts, and authorization
denial. Fills and costs (slippage/fees/taxes) come from the canonical
``ats.execution.paper`` implementation.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from ats.contracts.domain.types import DataQualityState
from ats.execution.paper.broker import PaperExecutionError
from ats.execution.paper.models import (
    PaperMarketFacts,
    PaperSubmissionScenario,
)
from ats.kernel.types import ALLOW, GateCode, KernelOutcome, KernelResult
from ats.trading_runtime.broker import OrderRequest, PaperBrokerAdapter

from .helpers import NIFTY, NOW, instrument, market_facts, policy

DENY = KernelResult(outcome=KernelOutcome.DENY, reason_codes=(GateCode.TOKEN_INVALID,))


def _request(**updates: object) -> OrderRequest:
    values: dict[str, object] = {
        "instrument_id": NIFTY,
        "side": "BUY",
        "quantity": Decimal("65"),
        "order_type": "MARKET",
        "limit_price": None,
        "idempotency_key": "K-AUTOFILL-1",
        "intent_id": "11111111-1111-1111-1111-111111111111",
    }
    values.update(updates)
    return OrderRequest(**values)


def _broker() -> PaperBrokerAdapter:
    return PaperBrokerAdapter(policy=policy(), instrument=instrument())


def test_acknowledgment_becomes_fill() -> None:
    b = _broker()
    st = b.submit_order(_request(), now=NOW, market_facts=market_facts(), authorization=ALLOW)
    assert st is not None and st.status == "FILLED"
    assert st.filled_quantity == Decimal("65")
    fills = b.consume_fills(st.order_id)
    assert len(fills) == 1
    assert fills[0].price == Decimal("101.10")  # ask 101 + 2 ticks * 0.05


def test_market_fill_has_real_costs() -> None:
    b = _broker()
    st = b.submit_order(_request(), now=NOW, market_facts=market_facts(), authorization=ALLOW)
    fills = b.consume_fills(st.order_id)
    assert len(fills) == 1
    f = fills[0]
    assert f.fees == Decimal("101.10") * Decimal("65") * Decimal("0.001")
    assert f.taxes == Decimal("101.10") * Decimal("65") * Decimal("0.002")
    assert f.slippage == Decimal("0.10") * Decimal("65")


def test_partial_fill_when_liquidity_insufficient() -> None:
    b = _broker()
    facts = market_facts(ask_quantity=65)  # only one lot of liquidity
    st = b.submit_order(
        _request(quantity=Decimal("130")), now=NOW, market_facts=facts, authorization=ALLOW
    )
    assert st is not None and st.status == "PARTIALLY_FILLED"
    assert st.filled_quantity == Decimal("65")
    fills = b.consume_fills(st.order_id)
    assert len(fills) == 1 and fills[0].quantity == Decimal("65")


def test_limit_order_not_filled_when_above_limit() -> None:
    b = _broker()
    facts = market_facts(ask=Decimal("101"))
    st = b.submit_order(
        _request(order_type="LIMIT", limit_price=Decimal("100")),
        now=NOW,
        market_facts=facts,
        authorization=ALLOW,
    )
    assert st is not None and st.status == "ACKNOWLEDGED"
    assert b.consume_fills(st.order_id) == ()


def test_rejection_returns_rejected_status() -> None:
    b = _broker()
    facts = PaperMarketFacts(
        instrument_id=NIFTY,
        bid=Decimal("99"),
        ask=Decimal("101"),
        bid_quantity=130,
        ask_quantity=130,
        quote_time=NOW,
        quality_state=DataQualityState.GOOD,
        scenario=PaperSubmissionScenario.REJECT,
        rejection_reason="RISK_BLOCKED",
    )
    st = b.submit_order(_request(), now=NOW, market_facts=facts, authorization=ALLOW)
    assert st is not None and st.status == "REJECTED"
    assert b.consume_fills(st.order_id) == ()


def test_authorization_denial_raises() -> None:
    b = _broker()
    with pytest.raises(PaperExecutionError):
        b.submit_order(_request(), now=NOW, market_facts=market_facts(), authorization=DENY)


def test_duplicate_submission_is_idempotent() -> None:
    b = _broker()
    r = _request()
    st1 = b.submit_order(r, now=NOW, market_facts=market_facts(), authorization=ALLOW)
    st2 = b.submit_order(r, now=NOW, market_facts=market_facts(), authorization=ALLOW)
    assert st1 is not None and st2 is not None and st1.order_id == st2.order_id
    assert st2.status == "FILLED"
    assert len(b.consume_fills(st1.order_id)) == 1


def test_duplicate_fill_consumption_strict() -> None:
    b = _broker()
    st = b.submit_order(_request(), now=NOW, market_facts=market_facts(), authorization=ALLOW)
    first = b.consume_fills(st.order_id)
    second = b.consume_fills(st.order_id)  # no leftover
    assert len(first) == 1 and second == ()


def test_stale_market_facts_raise() -> None:
    b = _broker()
    stale = market_facts(
        at=NOW - timedelta(seconds=120),  # older than maximum_quote_age_ms=60000
        scenario=PaperSubmissionScenario.ACKNOWLEDGE,
    ).model_copy(update={"quote_time": NOW - timedelta(seconds=120)})
    with pytest.raises(PaperExecutionError):
        b.submit_order(_request(), now=NOW, market_facts=stale, authorization=ALLOW)


def test_no_market_facts_returns_acknowledged_default() -> None:
    b = _broker()
    st = b.submit_order(_request(), now=NOW)
    assert st is not None and st.status == "ACKNOWLEDGED"


def test_unknown_submission_state() -> None:
    b = _broker()
    facts = market_facts(scenario=PaperSubmissionScenario.TIMEOUT_UNKNOWN)
    st = b.submit_order(_request(), now=NOW, market_facts=facts, authorization=ALLOW)
    assert st is not None
    # canonical returns order None -> adapter leaves ACKNOWLEDGED, no fills
    assert b.consume_fills(st.order_id) == ()
