"""Source-pinned Kronos adapter seam with no bundled model runtime."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal, Protocol

from ats.contracts.common import ATSBaseModel, FiniteFloat, UTCDateTime
from ats.contracts.domain.types import InstrumentId, NonEmptyStr, NonNegativeInt, PositiveInt
from ats.forecast.models import (
    ModelMetadata,
    ModelRunRequest,
    ProviderForecast,
    ResourceEvidence,
    next_observation_times,
)
from ats.forecast.provider import InsufficientContextError, ModelUnavailableError

KRONOS_SOURCE_REPOSITORY: Literal["shiyu-coder/Kronos"] = "shiyu-coder/Kronos"
KRONOS_SOURCE_REVISION: Literal["67b630e67f6a18c9e9be918d9b4337c960db1e9a"] = (
    "67b630e67f6a18c9e9be918d9b4337c960db1e9a"
)
KRONOS_MODEL_ID: Literal["NeoQuasar/Kronos-mini"] = "NeoQuasar/Kronos-mini"
KRONOS_MODEL_REVISION: Literal["f4e68697d9d5aed55cef5c96aabc3376bcad9f81"] = (
    "f4e68697d9d5aed55cef5c96aabc3376bcad9f81"
)
KRONOS_TOKENIZER_ID: Literal["NeoQuasar/Kronos-Tokenizer-2k"] = "NeoQuasar/Kronos-Tokenizer-2k"
KRONOS_TOKENIZER_REVISION: Literal["26966d0035065a0cae0ebad7af8ece35bc1fb51c"] = (
    "26966d0035065a0cae0ebad7af8ece35bc1fb51c"
)


class KronosLoadPolicy(ATSBaseModel):
    model_id: Literal["NeoQuasar/Kronos-mini"] = KRONOS_MODEL_ID
    model_revision: Literal["f4e68697d9d5aed55cef5c96aabc3376bcad9f81"] = KRONOS_MODEL_REVISION
    tokenizer_id: Literal["NeoQuasar/Kronos-Tokenizer-2k"] = KRONOS_TOKENIZER_ID
    tokenizer_revision: Literal["26966d0035065a0cae0ebad7af8ece35bc1fb51c"] = (
        KRONOS_TOKENIZER_REVISION
    )
    trust_remote_code: Literal[False] = False
    local_files_only: bool = True


class KronosRuntimeOutput(ATSBaseModel):
    instrument_id: InstrumentId
    timeframe: Literal["5m"]
    data_cutoff: UTCDateTime
    event_definition_id: NonEmptyStr
    horizon_bars: PositiveInt
    close_paths: tuple[tuple[FiniteFloat, ...], ...]
    runtime_ms: NonNegativeInt
    device: NonEmptyStr
    precision: NonEmptyStr
    model_loaded: bool


class KronosRuntime(Protocol):
    """Future audited runtime; implementations may translate to official OHLCVA frames."""

    def predict(
        self,
        request: ModelRunRequest,
        future_times: tuple[UTCDateTime, ...],
    ) -> KronosRuntimeOutput: ...


class KronosForecastProvider:
    """Normalize an injected official runtime; unavailable by default, never emulated."""

    def __init__(
        self,
        metadata: ModelMetadata,
        *,
        runtime: KronosRuntime | None = None,
        load_policy: KronosLoadPolicy | None = None,
    ) -> None:
        self._metadata = metadata
        self._runtime = runtime
        self.load_policy = load_policy or KronosLoadPolicy()

    @property
    def metadata(self) -> ModelMetadata:
        return self._metadata

    def forecast(self, request: ModelRunRequest) -> ProviderForecast:
        if self._runtime is None:
            raise ModelUnavailableError("audited Kronos runtime is not installed")
        if len(request.observations) < request.configuration.minimum_context:
            raise InsufficientContextError("Kronos context is below configured minimum")
        output = self._runtime.predict(request, next_observation_times(request))
        if output.close_paths:
            threshold = float(request.observations[-1].close)
            successes = sum(path[-1] > threshold for path in output.close_paths if path)
            probability = Decimal(successes) / Decimal(len(output.close_paths))
        else:
            probability = Decimal(0)
        return ProviderForecast(
            instrument_id=output.instrument_id,
            timeframe=output.timeframe,
            data_cutoff=output.data_cutoff,
            event_definition_id=output.event_definition_id,
            horizon_bars=output.horizon_bars,
            metadata=self.metadata,
            forecast_paths=output.close_paths,
            raw_probability=probability,
            uncertainty_method="kronos-sample-frequency",
            uncertainty_score=1.0 if len(output.close_paths) < 2 else 0.5,
            resource=ResourceEvidence(
                device=output.device,
                precision=output.precision,
                runtime_ms=output.runtime_ms,
                model_loaded=output.model_loaded,
                status="READY" if output.model_loaded else "UNAVAILABLE",
            ),
        )


__all__ = [
    "KRONOS_MODEL_ID",
    "KRONOS_MODEL_REVISION",
    "KRONOS_SOURCE_REPOSITORY",
    "KRONOS_SOURCE_REVISION",
    "KRONOS_TOKENIZER_ID",
    "KRONOS_TOKENIZER_REVISION",
    "KronosForecastProvider",
    "KronosLoadPolicy",
    "KronosRuntime",
    "KronosRuntimeOutput",
]
