from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from ats.forecast import ForecastObservation, ForecastWorker, NaiveForecastProvider
from ats.forecast.models import build_model_run_request

from tests.unit.forecast.fixtures import naive_metadata, observation, request


def test_future_appended_bars_cannot_change_cutoff_request_or_forecast() -> None:
    original = request()
    far_future = ForecastObservation(
        instrument_id="ABC",
        timeframe="5m",
        observation_time=original.data_cutoff + timedelta(days=1),
        open=Decimal("1000"),
        high=Decimal("1100"),
        low=Decimal("900"),
        close=Decimal("1050"),
        volume=Decimal("999999"),
        amount=None,
    )
    rebuilt = build_model_run_request(
        forecast_id=original.forecast_id,
        feature_bundle_id=original.feature_bundle_id,
        instrument_id=original.instrument_id,
        timeframe=original.timeframe,
        observations=(*original.observations, observation(4), far_future),
        as_of_time=original.as_of_time,
        data_cutoff=original.data_cutoff,
        event_definition=original.event_definition,
        horizon_bars=original.horizon_bars,
        configuration=original.configuration,
        started_at=original.started_at,
        completed_at=original.completed_at,
    )
    assert rebuilt == original
    worker = ForecastWorker(NaiveForecastProvider(naive_metadata()))
    assert worker.run(rebuilt) == worker.run(original)
