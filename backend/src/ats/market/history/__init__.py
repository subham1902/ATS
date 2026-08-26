"""Historical truth: immutable market history with explicit as-of gates.

This layer guarantees that replayed strategies can only observe information
that was genuinely available at the simulated decision time. It provides the
canonical :class:`MarketObservation` four-clock timeline, the immutable
:class:`DatasetManifest`, deterministic validation and quality classification,
tamper-evident persistence, and the :data:`AS_OF_INFORMATION_MODEL` admission
rule.
"""

from .as_of import (
    AsOfTimeline,
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
    InstrumentPolicyOverride,
    MarketBarPayload,
    MarketEventPayload,
    MarketObservation,
    ObservationKind,
    ObservationPayload,
    ObservationTimes,
    OptionChainQuotePayload,
    QualitySummary,
    RawRecordReference,
    TransformStep,
)
from .replay_bridge import (
    DEFAULT_HISTORY_TIME_SEMANTICS,
    AttributionRecord,
    HistoricalReplaySession,
    HistoryTimeSemantics,
    create_history_gated_replay,
    historical_bar_observations,
    historical_contract_metadata_observation,
    historical_event_observation,
    historical_option_quote_observation,
)
from .storage import (
    SavedDatasetPaths,
    load_historical_dataset,
    save_historical_dataset,
    verify_observation_integrity,
)
from .validation import validate_market_history

__all__ = [
    "AS_OF_INFORMATION_MODEL",
    "AsOfInformationModel",
    "AsOfTimeline",
    "AttributionRecord",
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
    "InstrumentPolicyOverride",
    "MarketBarPayload",
    "MarketEventPayload",
    "MarketObservation",
    "ObservationKind",
    "ObservationPayload",
    "ObservationTimes",
    "OptionChainQuotePayload",
    "QualitySummary",
    "RawRecordReference",
    "SavedDatasetPaths",
    "TransformStep",
    "build_historical_dataset",
    "build_market_observation",
    "create_history_gated_replay",
    "historical_bar_observations",
    "historical_contract_metadata_observation",
    "historical_event_observation",
    "historical_option_quote_observation",
    "is_admissible_as_of",
    "known_expiries_as_of",
    "latest_contract_metadata_as_of",
    "load_historical_dataset",
    "require_available",
    "save_historical_dataset",
    "validate_market_history",
    "verify_observation_integrity",
    "visible_observations",
]
