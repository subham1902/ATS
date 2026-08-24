"""Persistence baseline provider; an architecture oracle, not predictive intelligence."""

from __future__ import annotations

from decimal import Decimal

from .models import (
    ModelMetadata,
    ModelRunRequest,
    ProviderForecast,
    ResourceEvidence,
)
from .provider import InsufficientContextError

NAIVE_BASELINE_ID = "naive-last-close"
NAIVE_BASELINE_VERSION = "1.0.0"


class NaiveForecastProvider:
    """Repeat the last close with an explicitly uninformative event probability."""

    def __init__(self, metadata: ModelMetadata) -> None:
        self._metadata = metadata

    @property
    def metadata(self) -> ModelMetadata:
        return self._metadata

    def forecast(self, request: ModelRunRequest) -> ProviderForecast:
        if len(request.observations) < request.configuration.minimum_context:
            raise InsufficientContextError("naive provider has insufficient context")
        last_close = float(request.observations[-1].close)
        path = tuple(last_close for _ in range(request.horizon_bars))
        return ProviderForecast(
            instrument_id=request.instrument_id,
            timeframe=request.timeframe,
            data_cutoff=request.data_cutoff,
            event_definition_id=request.event_definition.event_definition_id,
            horizon_bars=request.horizon_bars,
            metadata=self.metadata,
            forecast_paths=(path,),
            raw_probability=Decimal("0.5"),
            uncertainty_method="uninformative-baseline",
            uncertainty_score=1.0,
            resource=ResourceEvidence(
                device="cpu",
                precision="float64",
                runtime_ms=0,
                model_loaded=True,
                status="READY",
            ),
        )


__all__ = ["NAIVE_BASELINE_ID", "NAIVE_BASELINE_VERSION", "NaiveForecastProvider"]
