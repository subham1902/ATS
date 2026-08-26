"""Zero-authority R&D Brain and Champion / Challenger research machinery."""

from .agent import HarnessResearchAgent
from .champion_challenger import ChampionChallengerRegistry
from .degradation import StrategyDegradationMonitor
from .engine import ResearchBrainEngine
from .hypothesis import build_research_hypothesis, validate_safe_formula_ast
from .models import (
    ChampionRecord,
    DegradationAction,
    DegradationAssessment,
    DegradationMetric,
    ExperimentProposal,
    ResearchHypothesis,
    ResearchRecommendation,
    ResearchRecommendationAction,
    StrategyLifecycleStatus,
)

__all__ = [
    "ChampionChallengerRegistry",
    "ChampionRecord",
    "DegradationAction",
    "DegradationAssessment",
    "DegradationMetric",
    "ExperimentProposal",
    "HarnessResearchAgent",
    "ResearchBrainEngine",
    "ResearchHypothesis",
    "ResearchRecommendation",
    "ResearchRecommendationAction",
    "StrategyDegradationMonitor",
    "StrategyLifecycleStatus",
    "build_research_hypothesis",
    "validate_safe_formula_ast",
]
