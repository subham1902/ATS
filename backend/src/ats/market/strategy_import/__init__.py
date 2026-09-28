"""ATS-BIN-01 Strategy Import and Tournament Subsystem."""

from .adapters import (
    ApexChimeraEngineAdapter,
    BaseImportedAdapter,
    BoomingBulls50AbsoluteAdapter,
    BoomingBullsHolyGrailAdapter,
    BoomingBullsMaxYieldAdapter,
    CrabelOrbNr7Adapter,
    CrudelePureFrameworkAdapter,
    DesianoBreakRetestAdapter,
    FabioAmtPlaybookAdapter,
    MarketSnapshotContext,
    StrategyAdapterProtocol,
    UnifiedMaster50PctAdapter,
    create_all_adapters,
)
from .decoder import StrategyDecoder, calc_entropy
from .models import (
    ImportedStrategyMetadata,
    ShadowMetrics,
    StrategyCompatibilityState,
    StrategyDecision,
    StrategyStatus,
)
from .tournament import ShadowTournamentEngine, ShadowTrajectory

__all__ = [
    "ApexChimeraEngineAdapter",
    "BaseImportedAdapter",
    "BoomingBulls50AbsoluteAdapter",
    "BoomingBullsHolyGrailAdapter",
    "BoomingBullsMaxYieldAdapter",
    "CrabelOrbNr7Adapter",
    "CrudelePureFrameworkAdapter",
    "DesianoBreakRetestAdapter",
    "FabioAmtPlaybookAdapter",
    "ImportedStrategyMetadata",
    "MarketSnapshotContext",
    "ShadowMetrics",
    "ShadowTournamentEngine",
    "ShadowTrajectory",
    "StrategyAdapterProtocol",
    "StrategyCompatibilityState",
    "StrategyDecision",
    "StrategyDecoder",
    "StrategyStatus",
    "UnifiedMaster50PctAdapter",
    "calc_entropy",
    "create_all_adapters",
]
