from __future__ import annotations

from decimal import Decimal

import pytest
from ats.contracts.domain.hashing import compute_payload_hash
from ats.contracts.domain.types import ForecastStatus
from ats.intelligence.ensemble import EnsembleInputError, build_ensemble_forecast

from .helpers import binding, configuration, context, weighted


def test_weighted_mean_and_binary_complement() -> None:
    ensemble = build_ensemble_forecast(
        market_context=context(),
        event_binding=binding(),
        horizon_bars=2,
        weighted_forecasts=(weighted(1, "0.8", 0.75), weighted(2, "0.4", 0.25)),
        configuration=configuration(),
    )
    assert ensemble.status is ForecastStatus.READY
    assert ensemble.raw_outcomes[0].probability == Decimal("0.70")
    assert ensemble.raw_outcomes[1].probability == Decimal("0.30")
    assert sum(item.probability for item in ensemble.raw_outcomes) == 1
    assert ensemble.payload_hash == compute_payload_hash(ensemble)


def test_weights_are_normalized_without_provider_privilege() -> None:
    ensemble = build_ensemble_forecast(
        market_context=context(),
        event_binding=binding(),
        horizon_bars=2,
        weighted_forecasts=(weighted(1, "0.8", 0.2), weighted(2, "0.4", 0.2)),
        configuration=configuration(),
    )
    assert tuple(item.weight for item in ensemble.members) == (0.5, 0.5)
    assert ensemble.raw_outcomes[0].probability == Decimal("0.6")


def test_failed_member_is_zero_weight_and_degrades() -> None:
    ensemble = build_ensemble_forecast(
        market_context=context(),
        event_binding=binding(),
        horizon_bars=2,
        weighted_forecasts=(
            weighted(1, "0.8", 0.5, baseline=True),
            weighted(2, None, 0.5, status=ForecastStatus.FAILED),
        ),
        configuration=configuration(),
    )
    assert ensemble.status is ForecastStatus.DEGRADED
    assert tuple(item.weight for item in ensemble.members) == (1.0, 0.0)
    assert ensemble.effective_member_count == 1
    assert ensemble.baseline_member_ids == (ensemble.members[0].forecast_id,)


def test_all_unusable_returns_bounded_failed_evidence() -> None:
    ensemble = build_ensemble_forecast(
        market_context=context(),
        event_binding=binding(),
        horizon_bars=2,
        weighted_forecasts=(weighted(1, None, 1.0, status=ForecastStatus.UNKNOWN),),
        configuration=configuration(),
    )
    assert ensemble.status is ForecastStatus.FAILED
    assert ensemble.raw_outcomes == ()
    assert ensemble.effective_member_count == 0


def test_disagreement_is_bounded_non_probability_score() -> None:
    ensemble = build_ensemble_forecast(
        market_context=context(),
        event_binding=binding(),
        horizon_bars=2,
        weighted_forecasts=(weighted(1, "0", 0.5), weighted(2, "1", 0.5)),
        configuration=configuration(),
    )
    assert ensemble.disagreement_score == 1.0


@pytest.mark.parametrize(
    "mutation",
    [
        "feature",
        "event",
        "horizon",
        "instrument",
        "timeframe",
        "as_of",
        "cutoff",
        "hash",
        "calibrated",
    ],
)
def test_lineage_mismatch_fails_closed(mutation: str) -> None:
    item = weighted(1, "0.7", 1.0)
    forecast = item.forecast
    if mutation == "feature":
        forecast = forecast.model_copy(update={"feature_bundle_id": context().snapshot_id})
    elif mutation == "event":
        forecast = forecast.model_copy(update={"event_definition_id": "OTHER"})
    elif mutation == "horizon":
        forecast = forecast.model_copy(update={"horizon_bars": 3})
    elif mutation in {"instrument", "timeframe", "as_of", "cutoff"}:
        key = {
            "instrument": "instrument_id",
            "timeframe": "timeframe",
            "as_of": "as_of_time",
            "cutoff": "data_cutoff",
        }[mutation]
        value = "OTHER" if mutation in {"instrument", "timeframe"} else "2026-08-24T03:00:00+00:00"
        forecast = forecast.model_copy(
            update={"raw_evidence": forecast.raw_evidence | {key: value}}
        )
    elif mutation == "hash":
        forecast = forecast.model_copy(update={"payload_hash": "0" * 64})
    elif mutation == "calibrated":
        forecast = forecast.model_copy(
            update={"calibrated_probability": Decimal("0.7"), "calibrator_version": "BAD"}
        )
    if mutation != "hash":
        forecast = forecast.model_copy(update={"payload_hash": compute_payload_hash(forecast)})
    with pytest.raises(EnsembleInputError):
        build_ensemble_forecast(
            market_context=context(),
            event_binding=binding(),
            horizon_bars=2,
            weighted_forecasts=(item.model_copy(update={"forecast": forecast}),),
            configuration=configuration(),
        )


def test_duplicate_forecast_and_outcomes_rejected() -> None:
    item = weighted(1, "0.7", 0.5)
    with pytest.raises(EnsembleInputError):
        build_ensemble_forecast(
            market_context=context(),
            event_binding=binding(),
            horizon_bars=2,
            weighted_forecasts=(item, item),
            configuration=configuration(),
        )
    duplicate_outcome = binding().model_copy(update={"complement_outcome_code": "ABOVE"})
    with pytest.raises(EnsembleInputError):
        build_ensemble_forecast(
            market_context=context(),
            event_binding=duplicate_outcome,
            horizon_bars=2,
            weighted_forecasts=(item,),
            configuration=configuration(),
        )


@pytest.mark.parametrize("horizon", [0, -1, True])
def test_invalid_horizon_rejected(horizon: int) -> None:
    with pytest.raises(EnsembleInputError):
        build_ensemble_forecast(
            market_context=context(),
            event_binding=binding(),
            horizon_bars=horizon,
            weighted_forecasts=(weighted(1, "0.7", 1.0),),
            configuration=configuration(),
        )
