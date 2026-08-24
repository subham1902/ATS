from __future__ import annotations

from ats.contracts.intelligence.models import EnsembleForecast
from ats.intelligence.ensemble import build_ensemble_forecast

from tests.unit.intelligence.ensemble.helpers import binding, configuration, context, weighted


def test_exact_frozen_ensemble_contract_and_schema() -> None:
    ensemble = build_ensemble_forecast(
        market_context=context(),
        event_binding=binding(),
        horizon_bars=2,
        weighted_forecasts=(weighted(1, "0.7", 1.0),),
        configuration=configuration(),
    )
    assert type(ensemble) is EnsembleForecast
    assert len(EnsembleForecast.model_fields) == 18
    assert EnsembleForecast.model_validate_json(ensemble.model_dump_json()) == ensemble
    assert EnsembleForecast.model_json_schema()["type"] == "object"


def test_no_calibrated_distribution_or_authority_fields() -> None:
    fields = set(EnsembleForecast.model_fields)
    assert fields.isdisjoint(
        {"calibrated_probability", "candidate", "risk_decision", "autonomy_token", "order_intent"}
    )
