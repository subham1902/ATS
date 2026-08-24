from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from ats.intelligence.strategy_lab.dataset_binding import DatasetBinding


def test_dataset_binding_valid() -> None:
    b = DatasetBinding(
        dataset_manifest_id=uuid4(),
        dataset_version="v1",
        dataset_cutoff=datetime(2024, 1, 10, tzinfo=UTC),
        strategy_definition_id=uuid4(),
        strategy_definition_version=1,
        formula_refs=((uuid4(), 1),),
        instrument_universe=("NSE_EQ-TCS",),
        timeframe="5m",  # type: ignore[arg-type]
        parameter_set_hash="a" * 64,
        seed=42,
        cost_model_version="v1",
    )
    assert b.instrument_universe[0] == "NSE_EQ-TCS"


def test_dataset_binding_rejects_empty_universe() -> None:
    with pytest.raises(Exception):
        DatasetBinding(
            dataset_manifest_id=uuid4(),
            dataset_version="v1",
            dataset_cutoff=datetime(2024, 1, 10, tzinfo=UTC),
            strategy_definition_id=uuid4(),
            strategy_definition_version=1,
            formula_refs=((uuid4(), 1),),
            instrument_universe=(),
            timeframe="5m",  # type: ignore[arg-type]
            parameter_set_hash="a" * 64,
            seed=42,
            cost_model_version="v1",
        )


def test_dataset_binding_no_implicit_latest() -> None:
    # Must explicitly bind dataset_version and cutoff
    b = DatasetBinding(
        dataset_manifest_id=uuid4(),
        dataset_version="v2",
        dataset_cutoff=datetime(2024, 1, 10, tzinfo=UTC),
        strategy_definition_id=uuid4(),
        strategy_definition_version=2,
        formula_refs=((uuid4(), 1), (uuid4(), 2)),
        instrument_universe=("NSE_EQ-INFY",),
        timeframe="5m",  # type: ignore[arg-type]
        parameter_set_hash="b" * 64,
        seed=1,
        cost_model_version="cost-v2",
    )
    assert b.dataset_version == "v2"
