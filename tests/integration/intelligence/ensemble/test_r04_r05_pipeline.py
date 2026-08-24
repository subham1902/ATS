from __future__ import annotations

from ats.contracts.domain.hashing import compute_payload_hash
from ats.forecast import ForecastWorker, NaiveForecastProvider
from ats.intelligence.ensemble import WeightedForecast, build_ensemble_forecast

from tests.unit.forecast.fixtures import naive_metadata, request
from tests.unit.intelligence.ensemble.helpers import binding, configuration, context


def test_r04_worker_output_enters_r05_without_calibration() -> None:
    model_request = request()
    forecast = ForecastWorker(NaiveForecastProvider(naive_metadata())).run(model_request)
    market_context = context().model_copy(
        update={
            "instrument_id": model_request.instrument_id,
            "feature_bundle_id": model_request.feature_bundle_id,
            "as_of_time": model_request.as_of_time,
            "data_cutoff": model_request.data_cutoff,
            "timeframe": model_request.timeframe,
        }
    )
    market_context = market_context.model_copy(
        update={"payload_hash": compute_payload_hash(market_context)}
    )
    ensemble = build_ensemble_forecast(
        market_context=market_context,
        event_binding=binding().model_copy(
            update={"forecast_event_code": model_request.event_definition.event_definition_id}
        ),
        horizon_bars=model_request.horizon_bars,
        weighted_forecasts=(
            WeightedForecast(forecast=forecast, configured_weight=1.0, baseline=True),
        ),
        configuration=configuration(),
    )
    assert ensemble.members[0].forecast_id == forecast.forecast_id
    assert ensemble.raw_outcomes
    assert forecast.calibrated_probability is None
