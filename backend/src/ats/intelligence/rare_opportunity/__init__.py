"""R10-X rare-opportunity and long-option convexity intelligence."""

from .engine import (
    assess_rare_opportunity,
    encode_pattern_state,
    find_historical_analogues,
    material_wake_for,
)
from .models import (
    AnalogueDistribution,
    AnalogueSupport,
    HistoricalAnalogue,
    OpportunityClass,
    OptionConvexityInput,
    PatternState,
    RareOpportunityAssessment,
    RareOpportunityPolicy,
)

__all__ = [
    "AnalogueDistribution",
    "AnalogueSupport",
    "HistoricalAnalogue",
    "OpportunityClass",
    "OptionConvexityInput",
    "PatternState",
    "RareOpportunityAssessment",
    "RareOpportunityPolicy",
    "assess_rare_opportunity",
    "encode_pattern_state",
    "find_historical_analogues",
    "material_wake_for",
]
