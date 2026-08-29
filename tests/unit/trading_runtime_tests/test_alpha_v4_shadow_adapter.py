from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

from ats.intelligence.alpha_v4 import AlphaAction, AlphaOptionQuote
from ats.trading_runtime.alpha_v4_shadow import AlphaV4ForwardShadowAdapter


def _update(at: datetime, price: str = "24000") -> SimpleNamespace:
    return SimpleNamespace(
        last_traded_price=Decimal(price),
        price_source_timestamp=at,
        exchange_timestamp=at,
        received_at=at + timedelta(milliseconds=20),
    )


def _warm_adapter() -> tuple[AlphaV4ForwardShadowAdapter, datetime]:
    adapter = AlphaV4ForwardShadowAdapter()
    start = datetime(2026, 8, 28, 4, 0, tzinfo=UTC)
    for minute in range(31):
        at = start + timedelta(minutes=minute)
        adapter.ingest("NIFTY", _update(at, str(24000 + minute * 5)))  # type: ignore[arg-type]
    return adapter, start + timedelta(minutes=30, milliseconds=20)


def test_live_adapter_keeps_directional_research_but_fails_economics_closed() -> None:
    adapter, decision_time = _warm_adapter()
    quote = AlphaOptionQuote("NSE_FO|CE", "CE", "2026-09-03", 24000.0, 99.9, 100.0, decision_time)

    decision = adapter.evaluate(
        underlying="NIFTY",
        decision_time=decision_time,
        ce_quote=quote,
        pe_quote=None,
        provider_lot_size=65,
    )
    telemetry = adapter.telemetry(
        decision,
        market_state_id="market-1",
        feature_bundle_id="features-1",
        decision_time=decision_time,
    )

    assert decision.recommended_action is AlphaAction.HOLD
    assert decision.reason == "ECONOMIC_PAYOFF_EVIDENCE_UNAVAILABLE"
    assert decision.expected_value is None
    assert telemetry["net_expected_value"] is None
    assert telemetry["directional_state"] == "DIRECTIONAL_RESEARCH_ONLY"
    assert telemetry["status"] == "SHADOW_ONLY"


def test_live_adapter_does_not_repair_invalid_provider_clock_order() -> None:
    adapter = AlphaV4ForwardShadowAdapter()
    at = datetime(2026, 8, 28, 4, 0, tzinfo=UTC)
    invalid = _update(at)
    invalid.received_at = at - timedelta(milliseconds=1)
    adapter.ingest("NIFTY", invalid)  # type: ignore[arg-type]

    decision = adapter.evaluate(
        underlying="NIFTY",
        decision_time=at,
        ce_quote=None,
        pe_quote=None,
        provider_lot_size=None,
    )

    assert decision.recommended_action is AlphaAction.HOLD
    assert decision.reason == "INVALID_TEMPORAL_EVIDENCE"


def test_live_adapter_rejects_stale_option_on_strong_directional_state() -> None:
    adapter, decision_time = _warm_adapter()
    stale = AlphaOptionQuote(
        "NSE_FO|CE",
        "CE",
        "2026-09-03",
        24000.0,
        99.9,
        100.0,
        decision_time - timedelta(milliseconds=2001),
    )

    decision = adapter.evaluate(
        underlying="NIFTY",
        decision_time=decision_time,
        ce_quote=stale,
        pe_quote=None,
        provider_lot_size=65,
    )

    assert decision.recommended_action is AlphaAction.HOLD
    assert decision.reason == "STALE_OPTION_EVIDENCE"


def test_live_adapter_isolates_alpha_model_failure(monkeypatch) -> None:
    adapter, decision_time = _warm_adapter()

    def fail(**_kwargs):
        raise RuntimeError("injected shadow failure")

    monkeypatch.setattr(
        "ats.trading_runtime.alpha_v4_shadow.evaluate_alpha_v4",
        lambda *_args, **kwargs: fail(**kwargs),
    )
    decision = adapter.evaluate(
        underlying="NIFTY",
        decision_time=decision_time,
        ce_quote=None,
        pe_quote=None,
        provider_lot_size=None,
    )

    assert decision.recommended_action is AlphaAction.HOLD
    assert decision.reason == "SHADOW_FAILED"
    assert decision.expected_value is None
