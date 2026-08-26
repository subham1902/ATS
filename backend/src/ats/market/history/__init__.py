"""Historical truth: immutable market history with explicit as-of gates.

This layer guarantees that replayed strategies can only observe information
that was genuinely available at the simulated decision time. It provides the
canonical :class:`MarketObservation` four-clock timeline, the immutable
:class:`DatasetManifest`, deterministic validation and quality classification,
and the :data:`AS_OF_INFORMATION_MODEL` admission rule.
"""

from .as_of import (
    is_admissible_as_of,
    known_expiries_as_of,
    latest_contract_metadata_as_of,
    require_available,
    visible_observations,
)
from .builder import build_historical_dataset, build_market_observation
from .dataset import HistoricalDataset
from .errors import (
    FutureInformationError,
    HistoricalTruthError,
    HistoricalTruthErrorCode,
)
from .models import (
    AS_OF_INFORMATION_MODEL,
    AsOfInformationModel,
    ContractMetadataPayload,
    DatasetManifest,
    DatasetSourceClass,
    FileHashEntry,
    HistoricalEventClass,
    HistoricalOptionType,
    HistoryFinding,
    HistoryValidationPolicy,
    HistoryValidationReport,
    MarketBarPayload,
    MarketEventPayload,
    MarketObservation,
    ObservationKind,
    ObservationTimes,
    OptionChainQuotePayload,
    QualitySummary,
    RawRecordReference,
    TransformStep,
)
from .replay_bridge import (
    DEFAULT_HISTORY_TIME_SEMANTICS,
    HistoricalReplaySession,
    HistoryTimeSemantics,
    create_history_gated_replay,
    historical_bar_observations,
)
from .validation import validate_market_history

__all__ = [
    "AS_OF_INFORMATION_MODEL",
    "AsOfInformationModel",
    "ContractMetadataPayload",
    "DEFAULT_HISTORY_TIME_SEMANTICS",
    "DatasetManifest",
    "DatasetSourceClass",
    "FileHashEntry",
    "FutureInformationError",
    "HistoricalDataset",
    "HistoricalEventClass",
    "HistoricalOptionType",
    "HistoricalReplaySession",
    "HistoricalTruthError",
    "HistoricalTruthErrorCode",
    "HistoryFinding",
    "HistoryTimeSemantics",
    "HistoryValidationPolicy",
    "HistoryValidationReport",
    "MarketBarPayload",
    "MarketEventPayload",
    "MarketObservation",
    "ObservationKind",
    "ObservationTimes",
    "OptionChainQuotePayload",
    "QualitySummary",
    "RawRecordReference",
    "TransformStep",
    "build_historical_dataset",
    "build_market_observation",
    "create_history_gated_replay",
    "historical_bar_observations",
    "is_admissible_as_of",
    "known_expiries_as_of",
    "latest_contract_metadata_as_of",
    "require_available",
    "validate_market_history",
    "visible_observations",
]
