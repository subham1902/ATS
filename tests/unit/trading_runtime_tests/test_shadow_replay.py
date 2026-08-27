"""Automated unit test suite for ATS Historical Shadow Session Replay Engine."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from ats.market.history import load_historical_dataset
from ats.market.history.models import MarketBarPayload
from scripts.run_ats_shadow_replay import run_shadow_session_replay

HISTORICAL_DIR = Path(r"D:\Projects\ATS\ats\data\historical")
NIFTY_DS_PATH = HISTORICAL_DIR / "nifty_options_a2_replay_v1"
BANKNIFTY_DS_PATH = HISTORICAL_DIR / "banknifty_options_a2_replay_v1"


def test_historical_truth_datasets_exist_and_pass_contracts() -> None:
    nifty_ds = load_historical_dataset(NIFTY_DS_PATH)
    bn_ds = load_historical_dataset(BANKNIFTY_DS_PATH)

    assert len(nifty_ds.observations) == 4235
    assert len(bn_ds.observations) == 4235

    assert nifty_ds.manifest.data_classification.value == "REAL_SOURCE"
    assert bn_ds.manifest.data_classification.value == "REAL_SOURCE"


def test_four_clock_no_lookahead_contract() -> None:
    nifty_ds = load_historical_dataset(NIFTY_DS_PATH)
    for obs in nifty_ds.observations:
        t = obs.times
        assert t.event_time <= t.source_time <= t.ingest_time <= t.available_to_strategy_time
        assert t.available_to_strategy_time > t.event_time


def test_shadow_replay_execution_invariants_and_determinism() -> None:
    run1 = run_shadow_session_replay(mode="NORMAL", capital=Decimal("100000"))
    run2 = run_shadow_session_replay(mode="NORMAL", capital=Decimal("100000"))

    assert run1["events_processed"] == 8450
    assert run2["events_processed"] == 8450

    assert run1["scanner_observations"] == 364
    assert run2["scanner_observations"] == 364

    assert run1["candidates_rejected"] == 728
    assert run2["candidates_rejected"] == 728

    assert run1["realized_pnl"] == "0"
    assert run2["realized_pnl"] == "0"

    assert run1 == run2, "Replay must be 100% deterministic across multiple runs"
