"""Provider isolation, untrusted-output validation, and A02 normalization."""

from __future__ import annotations

import math
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from decimal import Decimal

from pydantic import ValidationError

from ats.contracts.domain.hashing import compute_payload_hash
from ats.contracts.domain.models import ForecastBundle
from ats.contracts.domain.types import (
    BaselineResult,
    ForecastStatus,
    JsonValue,
    UncertaintyEvidence,
)
from ats.contracts.hashing import canonical_sha256

from .models import ModelRunRequest, ProviderForecast
from .naive import NAIVE_BASELINE_ID, NAIVE_BASELINE_VERSION
from .provider import (
    DeviceUnavailableError,
    ForecastProvider,
    InsufficientContextError,
    ModelUnavailableError,
    ProviderOutOfMemoryError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)

_UNKNOWN_FAILURES = {
    ProviderUnavailableError: "PROVIDER_UNAVAILABLE",
    ModelUnavailableError: "MODEL_UNAVAILABLE",
    DeviceUnavailableError: "DEVICE_UNAVAILABLE",
    InsufficientContextError: "INSUFFICIENT_CONTEXT",
}


class ForecastWorker:
    """Run one specialist provider and fail closed at the ForecastBundle boundary."""

    def __init__(self, provider: ForecastProvider) -> None:
        self._provider = provider

    def run(self, request: ModelRunRequest) -> ForecastBundle:
        executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="forecast-provider")
        future = executor.submit(self._provider.forecast, request)
        try:
            output = future.result(timeout=request.configuration.timeout_ms / 1000)
        except FutureTimeoutError:
            future.cancel()
            return self._failure(request, "TIMEOUT", ForecastStatus.FAILED)
        except tuple(_UNKNOWN_FAILURES) as exc:
            return self._failure(request, _UNKNOWN_FAILURES[type(exc)], ForecastStatus.UNKNOWN)
        except ProviderTimeoutError:
            return self._failure(request, "TIMEOUT", ForecastStatus.FAILED)
        except (ProviderOutOfMemoryError, MemoryError):
            return self._failure(request, "OUT_OF_MEMORY", ForecastStatus.FAILED)
        except Exception:
            return self._failure(request, "PROVIDER_EXCEPTION", ForecastStatus.FAILED)
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

        try:
            failure = self._validate_output(request, output)
        except Exception:
            return self._failure(request, "MALFORMED_OUTPUT", ForecastStatus.FAILED)
        if failure is not None:
            return self._failure(request, failure, ForecastStatus.FAILED)
        try:
            return self._ready(request, output)
        except ValidationError:
            return self._failure(
                request,
                "CONTRACT_NORMALIZATION_FAILED",
                ForecastStatus.FAILED,
            )

    def _validate_output(self, request: ModelRunRequest, output: ProviderForecast) -> str | None:
        config = request.configuration
        metadata = output.metadata
        declared = self._provider.metadata
        if output.instrument_id != request.instrument_id:
            return "INSTRUMENT_MISMATCH"
        if output.timeframe != request.timeframe:
            return "TIMEFRAME_MISMATCH"
        if output.event_definition_id != request.event_definition.event_definition_id:
            return "EVENT_MISMATCH"
        if output.horizon_bars != request.horizon_bars:
            return "HORIZON_MISMATCH"
        if output.data_cutoff != request.data_cutoff:
            return "CUTOFF_MISMATCH"
        if metadata != declared:
            return "PROVIDER_METADATA_MISMATCH"
        if (
            metadata.model_id != config.model_id
            or metadata.model_version != config.model_version
            or metadata.checkpoint_hash != config.checkpoint_hash
            or metadata.method != config.method
            or metadata.seed != config.seed
        ):
            return "MODEL_VERSION_MISMATCH"
        if not output.resource.model_loaded or output.resource.status != "READY":
            return "MODEL_UNAVAILABLE"
        if not output.forecast_paths:
            return "BAD_SHAPE"
        if any(len(path) != request.horizon_bars for path in output.forecast_paths):
            return "BAD_SHAPE"
        if any(not math.isfinite(value) for path in output.forecast_paths for value in path):
            return "NONFINITE_OUTPUT"
        if not output.raw_probability.is_finite() or not Decimal(
            0
        ) <= output.raw_probability <= Decimal(1):
            return "MALFORMED_PROBABILITY"
        if not math.isfinite(output.uncertainty_score):
            return "NONFINITE_OUTPUT"
        return None

    def _ready(self, request: ModelRunRequest, output: ProviderForecast) -> ForecastBundle:
        metadata = output.metadata
        resource = output.resource
        baseline_results: tuple[BaselineResult, ...] = ()
        if metadata.provider_name == "naive":
            baseline_results = (
                BaselineResult(
                    baseline_id=NAIVE_BASELINE_ID,
                    baseline_version=NAIVE_BASELINE_VERSION,
                    probability=output.raw_probability,
                    metrics={},
                ),
            )
        raw_evidence: dict[str, JsonValue] = {
            "provider": metadata.provider_name,
            "method": metadata.method,
            "source_revision": metadata.source_revision,
            "instrument_id": request.instrument_id,
            "timeframe": request.timeframe,
            "as_of_time": request.as_of_time.isoformat(),
            "data_cutoff": request.data_cutoff.isoformat(),
            "history_hash": canonical_sha256(request.observations),
            "observation_count": len(request.observations),
            "device": resource.device,
            "precision": resource.precision,
            "runtime_ms": resource.runtime_ms,
            "model_loaded": resource.model_loaded,
            "resource_status": resource.status,
        }
        bundle = ForecastBundle(
            forecast_id=request.forecast_id,
            feature_bundle_id=request.feature_bundle_id,
            model_id=metadata.model_id,
            model_version=metadata.model_version,
            checkpoint_hash=metadata.checkpoint_hash,
            data_version=request.configuration.data_version,
            horizon_bars=request.horizon_bars,
            event_definition_id=request.event_definition.event_definition_id,
            raw_evidence=raw_evidence,
            forecast_paths=output.forecast_paths,
            raw_probability=output.raw_probability,
            calibrated_probability=None,
            calibrator_version=None,
            uncertainty=UncertaintyEvidence(
                method=output.uncertainty_method,
                score=output.uncertainty_score,
            ),
            baseline_results=baseline_results,
            seed=metadata.seed,
            status=ForecastStatus.READY,
            started_at=request.started_at,
            completed_at=request.completed_at,
            payload_hash="0" * 64,
        )
        return bundle.model_copy(update={"payload_hash": compute_payload_hash(bundle)})

    def _failure(
        self, request: ModelRunRequest, code: str, status: ForecastStatus
    ) -> ForecastBundle:
        config = request.configuration
        bundle = ForecastBundle(
            forecast_id=request.forecast_id,
            feature_bundle_id=request.feature_bundle_id,
            model_id=config.model_id,
            model_version=config.model_version,
            checkpoint_hash=config.checkpoint_hash,
            data_version=config.data_version,
            horizon_bars=request.horizon_bars,
            event_definition_id=request.event_definition.event_definition_id,
            raw_evidence={
                "failure_code": code,
                "instrument_id": request.instrument_id,
                "timeframe": request.timeframe,
                "as_of_time": request.as_of_time.isoformat(),
                "data_cutoff": request.data_cutoff.isoformat(),
                "history_hash": canonical_sha256(request.observations),
                "observation_count": len(request.observations),
                "model_loaded": False,
                "resource_status": "UNAVAILABLE",
            },
            forecast_paths=None,
            raw_probability=None,
            calibrated_probability=None,
            calibrator_version=None,
            uncertainty=UncertaintyEvidence(method="provider-failure", score=None),
            baseline_results=(),
            seed=config.seed,
            status=status,
            started_at=request.started_at,
            completed_at=request.completed_at,
            payload_hash="0" * 64,
        )
        return bundle.model_copy(update={"payload_hash": compute_payload_hash(bundle)})


__all__ = ["ForecastWorker"]
