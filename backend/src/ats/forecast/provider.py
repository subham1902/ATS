"""Narrow forecast provider protocol and explicit failure vocabulary."""

from __future__ import annotations

from typing import Protocol

from .models import ModelMetadata, ModelRunRequest, ProviderForecast


class ForecastProvider(Protocol):
    @property
    def metadata(self) -> ModelMetadata: ...

    def forecast(self, request: ModelRunRequest) -> ProviderForecast: ...


class ForecastProviderError(RuntimeError):
    """Base provider failure; never represents a valid forecast."""


class ProviderUnavailableError(ForecastProviderError):
    pass


class ModelUnavailableError(ForecastProviderError):
    pass


class DeviceUnavailableError(ForecastProviderError):
    pass


class InsufficientContextError(ForecastProviderError):
    pass


class ProviderTimeoutError(ForecastProviderError):
    pass


class ProviderOutOfMemoryError(ForecastProviderError):
    pass


__all__ = [
    "DeviceUnavailableError",
    "ForecastProvider",
    "ForecastProviderError",
    "InsufficientContextError",
    "ModelUnavailableError",
    "ProviderOutOfMemoryError",
    "ProviderTimeoutError",
    "ProviderUnavailableError",
]
