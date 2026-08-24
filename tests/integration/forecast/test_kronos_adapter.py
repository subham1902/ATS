from __future__ import annotations

from dataclasses import dataclass

from ats.contracts.domain.hashing import compute_payload_hash
from ats.contracts.domain.types import ForecastStatus
from ats.forecast import ForecastWorker, ModelMetadata, ModelRunRequest
from ats.kronos_worker import (
    KRONOS_MODEL_ID,
    KRONOS_MODEL_REVISION,
    KRONOS_SOURCE_REVISION,
    KRONOS_TOKENIZER_REVISION,
    KronosForecastProvider,
    KronosLoadPolicy,
    KronosRuntimeOutput,
)

from tests.unit.forecast.fixtures import request


def kronos_metadata() -> ModelMetadata:
    return ModelMetadata(
        provider_name="kronos",
        model_id=KRONOS_MODEL_ID,
        model_version="0.1.0",
        checkpoint_hash="b" * 64,
        method="official-kline-sampling",
        seed=11,
        source_revision=KRONOS_SOURCE_REVISION,
    )


@dataclass
class AuditedRuntimeStub:
    received_times: tuple[object, ...] = ()

    def predict(
        self, model_request: ModelRunRequest, future_times: tuple[object, ...]
    ) -> KronosRuntimeOutput:
        self.received_times = future_times
        return KronosRuntimeOutput(
            instrument_id=model_request.instrument_id,
            timeframe=model_request.timeframe,
            data_cutoff=model_request.data_cutoff,
            event_definition_id=model_request.event_definition.event_definition_id,
            horizon_bars=model_request.horizon_bars,
            close_paths=((104.0, 105.0), (104.0, 102.0)),
            runtime_ms=7,
            device="cpu",
            precision="float32",
            model_loaded=True,
        )


def test_kronos_adapter_normalizes_only_bounded_output() -> None:
    metadata = kronos_metadata()
    model_request = request(metadata=metadata)
    runtime = AuditedRuntimeStub()
    bundle = ForecastWorker(KronosForecastProvider(metadata, runtime=runtime)).run(model_request)
    assert bundle.status is ForecastStatus.READY
    assert bundle.raw_probability is not None
    assert str(bundle.raw_probability) == "0.5"
    assert bundle.forecast_paths == ((104.0, 105.0), (104.0, 102.0))
    assert bundle.raw_evidence["provider"] == "kronos"
    assert len(runtime.received_times) == model_request.horizon_bars
    assert bundle.payload_hash == compute_payload_hash(bundle)


def test_uninstalled_kronos_runtime_is_explicitly_unknown() -> None:
    metadata = kronos_metadata()
    bundle = ForecastWorker(KronosForecastProvider(metadata)).run(request(metadata=metadata))
    assert bundle.status is ForecastStatus.UNKNOWN
    assert bundle.forecast_paths is None
    assert bundle.raw_evidence["failure_code"] == "MODEL_UNAVAILABLE"


def test_kronos_loading_policy_is_revision_pinned_and_remote_code_disabled() -> None:
    policy = KronosLoadPolicy()
    assert policy.model_id == KRONOS_MODEL_ID
    assert policy.model_revision == KRONOS_MODEL_REVISION
    assert policy.tokenizer_revision == KRONOS_TOKENIZER_REVISION
    assert policy.trust_remote_code is False
    assert policy.local_files_only is True
