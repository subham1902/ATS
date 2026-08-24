from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from time import sleep

import pytest
from ats.contracts.domain.types import ForecastStatus
from ats.forecast import (
    DeviceUnavailableError,
    ForecastWorker,
    ModelUnavailableError,
    ProviderOutOfMemoryError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from ats.forecast.models import (
    ModelMetadata,
    ModelRunRequest,
    ProviderForecast,
    ResourceEvidence,
)
from pydantic import ValidationError

from tests.unit.forecast.fixtures import configuration, naive_metadata, observation, request


def valid_output(model_request: ModelRunRequest) -> ProviderForecast:
    return ProviderForecast(
        instrument_id=model_request.instrument_id,
        timeframe=model_request.timeframe,
        data_cutoff=model_request.data_cutoff,
        event_definition_id=model_request.event_definition.event_definition_id,
        horizon_bars=model_request.horizon_bars,
        metadata=naive_metadata(),
        forecast_paths=((1.0, 2.0),),
        raw_probability=Decimal("0.5"),
        uncertainty_method="test",
        uncertainty_score=0.5,
        resource=ResourceEvidence(
            device="cpu",
            precision="float64",
            runtime_ms=1,
            model_loaded=True,
            status="READY",
        ),
    )


@dataclass
class OutputProvider:
    metadata: ModelMetadata
    output: ProviderForecast

    def forecast(self, request: ModelRunRequest) -> ProviderForecast:
        del request
        return self.output


@pytest.mark.parametrize(
    ("change", "code"),
    [
        ({"instrument_id": "XYZ"}, "INSTRUMENT_MISMATCH"),
        ({"timeframe": "15m"}, "TIMEFRAME_MISMATCH"),
        ({"event_definition_id": "other-event"}, "EVENT_MISMATCH"),
        ({"horizon_bars": 3}, "HORIZON_MISMATCH"),
        ({"data_cutoff": request().data_cutoff - timedelta(minutes=5)}, "CUTOFF_MISMATCH"),
    ],
)
def test_output_binding_mismatch_fails(change: dict[str, object], code: str) -> None:
    model_request = request()
    output = valid_output(model_request).model_copy(update=change)
    bundle = ForecastWorker(OutputProvider(naive_metadata(), output)).run(model_request)
    assert bundle.status is ForecastStatus.FAILED
    assert bundle.raw_evidence["failure_code"] == code


def test_model_version_mismatch_fails() -> None:
    model_request = request()
    wrong = naive_metadata().model_copy(update={"model_version": "2.0.0"})
    provider = OutputProvider(
        wrong, valid_output(model_request).model_copy(update={"metadata": wrong})
    )
    bundle = ForecastWorker(provider).run(model_request)
    assert bundle.raw_evidence["failure_code"] == "MODEL_VERSION_MISMATCH"


@pytest.mark.parametrize(
    ("paths", "code"),
    [
        ((), "BAD_SHAPE"),
        (((1.0,),), "BAD_SHAPE"),
        (((1.0, float("nan")),), "NONFINITE_OUTPUT"),
        (((1.0, float("inf")),), "NONFINITE_OUTPUT"),
    ],
)
def test_bad_shape_and_nonfinite_output_fail_closed(
    paths: tuple[tuple[float, ...], ...], code: str
) -> None:
    model_request = request()
    output = valid_output(model_request).model_copy(update={"forecast_paths": paths})
    bundle = ForecastWorker(OutputProvider(naive_metadata(), output)).run(model_request)
    assert bundle.status is ForecastStatus.FAILED
    assert bundle.raw_evidence["failure_code"] == code


@dataclass
class RaisingProvider:
    metadata: ModelMetadata
    exception: Exception

    def forecast(self, request: ModelRunRequest) -> ProviderForecast:
        del request
        raise self.exception


@pytest.mark.parametrize(
    ("exception", "status", "code"),
    [
        (ProviderUnavailableError(), ForecastStatus.UNKNOWN, "PROVIDER_UNAVAILABLE"),
        (ModelUnavailableError(), ForecastStatus.UNKNOWN, "MODEL_UNAVAILABLE"),
        (DeviceUnavailableError(), ForecastStatus.UNKNOWN, "DEVICE_UNAVAILABLE"),
        (ProviderTimeoutError(), ForecastStatus.FAILED, "TIMEOUT"),
        (ProviderOutOfMemoryError(), ForecastStatus.FAILED, "OUT_OF_MEMORY"),
        (RuntimeError(), ForecastStatus.FAILED, "PROVIDER_EXCEPTION"),
    ],
)
def test_provider_failure_matrix(exception: Exception, status: ForecastStatus, code: str) -> None:
    bundle = ForecastWorker(RaisingProvider(naive_metadata(), exception)).run(request())
    assert bundle.status is status
    assert bundle.raw_evidence["failure_code"] == code
    assert bundle.forecast_paths is None


class SlowProvider(OutputProvider):
    def forecast(self, request: ModelRunRequest) -> ProviderForecast:
        sleep(0.03)
        return super().forecast(request)


def test_worker_enforces_timeout() -> None:
    model_request = request().model_copy(
        update={"configuration": configuration().model_copy(update={"timeout_ms": 1})}
    )
    bundle = ForecastWorker(SlowProvider(naive_metadata(), valid_output(model_request))).run(
        model_request
    )
    assert bundle.status is ForecastStatus.FAILED
    assert bundle.raw_evidence["failure_code"] == "TIMEOUT"


def test_request_rejects_future_and_identity_mismatch() -> None:
    original = request()
    with pytest.raises(ValidationError, match="exceeds data_cutoff"):
        ModelRunRequest.model_validate(
            {
                **original.model_dump(),
                "observations": (*original.observations, observation(4)),
            }
        )
    with pytest.raises(ValidationError, match="instrument mismatch"):
        request(observations=(observation(0, instrument="XYZ"), observation(1)))


def test_configuration_rejects_unsupported_horizon() -> None:
    original = request()
    with pytest.raises(ValidationError, match="not supported"):
        ModelRunRequest.model_validate({**original.model_dump(), "horizon_bars": 99})
