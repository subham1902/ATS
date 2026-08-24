"""Deterministic analytical feature computation over completed market snapshots."""

from .engine import compute_feature_bundle
from .errors import FeatureComputationError, FeatureInputError, FeatureNumericError
from .registry import (
    V1_FEATURE_CODES,
    V1_FEATURE_REGISTRY,
    FeatureConfiguration,
    FeatureDefinition,
    FeatureOutputSemantic,
)

__all__ = [
    "FeatureComputationError",
    "FeatureConfiguration",
    "FeatureDefinition",
    "FeatureInputError",
    "FeatureNumericError",
    "FeatureOutputSemantic",
    "V1_FEATURE_CODES",
    "V1_FEATURE_REGISTRY",
    "compute_feature_bundle",
]
