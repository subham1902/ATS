"""Historical-truth public-surface and purity contract tests."""

from __future__ import annotations

from pathlib import Path

import ats.market.history as history_module
from ats.market.history import (
    AS_OF_INFORMATION_MODEL,
    DatasetManifest,
    HistoricalDataset,
    HistoryValidationReport,
    MarketObservation,
)

EXPECTED_HISTORY_ALL = (
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
)

_FORBIDDEN_PURITY_TOKENS = (
    "SystemClock",
    "datetime.now(",
    "time.time(",
    "time.gmtime(",
    "random.",
    "urlopen(",
    "requests.",
)


def test_public_history_surface_is_locked() -> None:
    assert tuple(sorted(history_module.__all__)) == EXPECTED_HISTORY_ALL


def test_core_models_expose_json_schema() -> None:
    versioned_models = (MarketObservation, DatasetManifest, HistoricalDataset)
    for model in (*versioned_models, HistoryValidationReport):
        assert model.model_json_schema()["type"] == "object"
    for model in versioned_models:
        assert model.model_fields["schema_version"].default == "1.0"


def test_as_of_information_model_is_the_declared_admission_contract() -> None:
    assert AS_OF_INFORMATION_MODEL.schema_version == "1.0"
    assert AS_OF_INFORMATION_MODEL.availability_field == "times.available_to_strategy_time"
    assert (
        AS_OF_INFORMATION_MODEL.admission_rule
        == "observation.times.available_to_strategy_time <= decision_time"
    )


def test_history_layer_is_wall_clock_free_and_pure() -> None:
    package_dir = Path("backend/src/ats/market/history")
    sources = sorted(package_dir.glob("*.py"))
    assert len(sources) >= 6
    for source in sources:
        text = source.read_text(encoding="utf-8")
        for token in _FORBIDDEN_PURITY_TOKENS:
            assert token not in text, f"{source.name} contains forbidden token {token!r}"


def test_b01_replay_public_surface_remains_unchanged() -> None:
    from ats.market.replay.engine import DeterministicReplay

    public = {name for name in dir(DeterministicReplay) if not name.startswith("_")}
    assert public == {
        "advance",
        "clock",
        "current",
        "snapshot_at",
        "state",
        "visible_snapshots",
    }
