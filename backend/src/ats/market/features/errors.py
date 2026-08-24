"""Explicit fail-closed errors for deterministic feature computation."""


class FeatureComputationError(ValueError):
    """Base error for invalid feature inputs or unsafe computation."""


class FeatureInputError(FeatureComputationError):
    """Snapshot history or cutoff is invalid."""


class FeatureNumericError(FeatureComputationError):
    """An analytical result cannot cross the finite-float boundary."""


__all__ = ["FeatureComputationError", "FeatureInputError", "FeatureNumericError"]
