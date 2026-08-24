from __future__ import annotations

from ats.intelligence.ensemble import build_ensemble_forecast

from tests.unit.intelligence.ensemble.helpers import binding, configuration, context, weighted


def test_repeated_inputs_are_deterministic() -> None:
    inputs = (weighted(1, "0.7", 0.6), weighted(2, "0.4", 0.4))
    first = build_ensemble_forecast(
        market_context=context(),
        event_binding=binding(),
        horizon_bars=2,
        weighted_forecasts=inputs,
        configuration=configuration(),
    )
    second = build_ensemble_forecast(
        market_context=context(),
        event_binding=binding(),
        horizon_bars=2,
        weighted_forecasts=inputs,
        configuration=configuration(),
    )
    assert first == second
    assert first.model_dump_json() == second.model_dump_json()


def test_member_input_order_has_explicit_stable_semantics() -> None:
    inputs = (weighted(1, "0.7", 0.6), weighted(2, "0.4", 0.4))
    first = build_ensemble_forecast(
        market_context=context(),
        event_binding=binding(),
        horizon_bars=2,
        weighted_forecasts=inputs,
        configuration=configuration(),
    )
    second = build_ensemble_forecast(
        market_context=context(),
        event_binding=binding(),
        horizon_bars=2,
        weighted_forecasts=tuple(reversed(inputs)),
        configuration=configuration(),
    )
    assert first.raw_outcomes == second.raw_outcomes
    assert first.disagreement_score == second.disagreement_score


def test_no_member_has_permanent_model_privilege() -> None:
    first = build_ensemble_forecast(
        market_context=context(),
        event_binding=binding(),
        horizon_bars=2,
        weighted_forecasts=(weighted(1, "0.9", 0.2), weighted(2, "0.1", 0.8)),
        configuration=configuration(),
    )
    second = build_ensemble_forecast(
        market_context=context(),
        event_binding=binding(),
        horizon_bars=2,
        weighted_forecasts=(weighted(1, "0.9", 0.8), weighted(2, "0.1", 0.2)),
        configuration=configuration(),
    )
    assert first.raw_outcomes[0].probability != second.raw_outcomes[0].probability
