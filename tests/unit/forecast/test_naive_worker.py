from __future__ import annotations

from dataclasses import dataclass

import ats.forecast.worker as worker_module
import pytest
from ats.contracts.domain.hashing import compute_payload_hash
from ats.contracts.domain.types import BaselineResult, ForecastStatus
from ats.forecast import ForecastProvider, ForecastWorker, NaiveForecastProvider
from ats.forecast.models import ModelMetadata, ModelRunRequest, ProviderForecast
from ats.forecast.naive import NAIVE_BASELINE_ID, NAIVE_BASELINE_VERSION
from pydantic import ValidationError

from tests.unit.forecast.fixtures import naive_metadata, observation, request


def test_naive_output_is_deterministic_and_canonical() -> None:
    worker = ForecastWorker(NaiveForecastProvider(naive_metadata()))
    model_request = request()
    first = worker.run(model_request)
    second = worker.run(model_request)
    assert first == second
    assert first.status is ForecastStatus.READY
    assert first.forecast_paths == ((103.5, 103.5),)
    assert first.payload_hash == compute_payload_hash(first)
    assert first.baseline_results[0].baseline_id == "naive-last-close"


def test_metadata_and_lineage_are_preserved() -> None:
    metadata = naive_metadata()
    bundle = ForecastWorker(NaiveForecastProvider(metadata)).run(request())
    assert bundle.model_id == metadata.model_id
    assert bundle.model_version == metadata.model_version
    assert bundle.checkpoint_hash == metadata.checkpoint_hash
    assert bundle.seed == metadata.seed
    assert bundle.event_definition_id == "close-above-last-v1"
    assert bundle.raw_evidence["provider"] == "naive"
    assert bundle.raw_evidence["observation_count"] == 4


@pytest.mark.parametrize("model_version", ["1", "build-2026-08-24", "v-next", "1.0.0"])
def test_arbitrary_model_version_preserved_with_owned_baseline_semver(
    model_version: str,
) -> None:
    metadata = naive_metadata().model_copy(update={"model_version": model_version})
    bundle = ForecastWorker(NaiveForecastProvider(metadata)).run(request(metadata=metadata))
    assert bundle.status is ForecastStatus.READY
    assert bundle.model_version == model_version
    assert bundle.baseline_results == (
        BaselineResult(
            baseline_id=NAIVE_BASELINE_ID,
            baseline_version=NAIVE_BASELINE_VERSION,
            probability=bundle.raw_probability,
            metrics={},
        ),
    )


def test_baseline_normalization_error_is_bounded_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(ValidationError) as failure:
        BaselineResult(
            baseline_id=NAIVE_BASELINE_ID,
            baseline_version="not-semver",
            probability=None,
            metrics={},
        )
    normalization_error = failure.value

    def malformed_baseline(**values: object) -> BaselineResult:
        del values
        raise normalization_error

    monkeypatch.setattr(worker_module, "BaselineResult", malformed_baseline)
    bundle = ForecastWorker(NaiveForecastProvider(naive_metadata())).run(request())
    assert bundle.status is ForecastStatus.FAILED
    assert bundle.forecast_paths is None
    assert bundle.raw_evidence["failure_code"] == "CONTRACT_NORMALIZATION_FAILED"


def test_non_semver_model_version_remains_deterministic() -> None:
    metadata = naive_metadata().model_copy(update={"model_version": "v-next"})
    worker = ForecastWorker(NaiveForecastProvider(metadata))
    model_request = request(metadata=metadata)
    assert worker.run(model_request) == worker.run(model_request)


def test_insufficient_context_is_unknown_without_forecast() -> None:
    model_request = request(observations=(observation(0),))
    bundle = ForecastWorker(NaiveForecastProvider(naive_metadata())).run(model_request)
    assert bundle.status is ForecastStatus.UNKNOWN
    assert bundle.forecast_paths is None
    assert bundle.raw_probability is None
    assert bundle.raw_evidence["failure_code"] == "INSUFFICIENT_CONTEXT"


def test_provider_protocol_has_no_authority_surface() -> None:
    assert ForecastProvider.__dict__.keys().isdisjoint(
        {
            "create_candidate",
            "assess_risk",
            "grant_autonomy",
            "create_order",
            "govern_campaign",
        }
    )
    assert set(ForecastProvider.__dict__) >= {"metadata", "forecast"}


@dataclass
class InvalidProvider:
    metadata: ModelMetadata
    value: object

    def forecast(self, request: ModelRunRequest) -> ProviderForecast:
        del request
        return self.value  # type: ignore[return-value]


@pytest.mark.parametrize("value", [None, {}, object()])
def test_malformed_provider_object_fails_closed(value: object) -> None:
    bundle = ForecastWorker(InvalidProvider(naive_metadata(), value)).run(request())
    assert bundle.status is ForecastStatus.FAILED
    assert bundle.raw_evidence["failure_code"] == "MALFORMED_OUTPUT"
