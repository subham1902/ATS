from __future__ import annotations

from dataclasses import dataclass

import pytest
from ats.contracts.domain.hashing import compute_payload_hash
from ats.contracts.domain.types import ForecastStatus
from ats.forecast import ForecastProvider, ForecastWorker, NaiveForecastProvider
from ats.forecast.models import ModelMetadata, ModelRunRequest, ProviderForecast

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
