from __future__ import annotations

import hashlib
import json
from importlib.resources import files

import pytest
from ats.market import (
    ApprovedFixture,
    ReplayManifest,
    nse_cash_alpha_v1_calendar,
)
from ats.market.fixtures.loader import _load_approved_fixture, _load_replay_dataset
from ats.market.replay.models import ReplayFixtureDocument
from pydantic import ValidationError


def fixture_bytes() -> bytes:
    return files("ats.market.fixtures").joinpath("nse_cash_reliance_5m_v1.bars.json").read_bytes()


def manifest() -> ReplayManifest:
    content = (
        files("ats.market.fixtures").joinpath("nse_cash_reliance_5m_v1.manifest.json").read_bytes()
    )
    return ReplayManifest.model_validate_json(content)


def test_approved_manifest_binds_every_required_identity_field() -> None:
    item = manifest()
    assert item.dataset_version == "1.0.0"
    assert item.instrument == "RELIANCE"
    assert (item.exchange, item.segment, item.timeframe) == ("NSE", "CASH", "5m")
    assert item.bar_count == 4
    assert item.calendar_id == "NSE_CASH_ALPHA"
    assert item.first_bar <= item.last_bar
    assert hashlib.sha256(fixture_bytes()).hexdigest() == item.content_sha256


def test_approved_fixture_loads_only_after_hash_and_calendar_validation() -> None:
    dataset = _load_approved_fixture(
        ApprovedFixture.NSE_CASH_RELIANCE_5M_V1,
        nse_cash_alpha_v1_calendar(),
    )
    assert len(dataset.bars) == dataset.manifest.bar_count == 4


def test_bad_fixture_hash_is_rejected_before_parsing() -> None:
    with pytest.raises(ValueError, match="SHA-256"):
        _load_replay_dataset(manifest(), fixture_bytes() + b" ", nse_cash_alpha_v1_calendar())


def test_calendar_version_mismatch_is_rejected() -> None:
    calendar = nse_cash_alpha_v1_calendar().model_copy(update={"calendar_version": "2.0.0"})
    with pytest.raises(ValueError, match="calendar"):
        _load_replay_dataset(manifest(), fixture_bytes(), calendar)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("exchange", "BSE"),
        ("segment", "FUTURES"),
        ("timeframe", "1m"),
    ],
)
def test_wrong_market_identity_is_structurally_rejected(field: str, value: str) -> None:
    raw = json.loads(fixture_bytes())
    raw["bars"][0][field] = value
    with pytest.raises(ValidationError):
        ReplayFixtureDocument.model_validate_json(json.dumps(raw))


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ({"duplicate": True}, "bar timestamps"),
        ({"reverse": True}, "timestamp ordered"),
        ({"sequence": 8}, "source sequence"),
    ],
)
def test_duplicate_out_of_order_and_sequence_discontinuity(
    mutation: dict[str, object], message: str
) -> None:
    raw = json.loads(fixture_bytes())
    if mutation.get("duplicate"):
        raw["bars"][1]["bar_timestamp"] = raw["bars"][0]["bar_timestamp"]
    if mutation.get("reverse"):
        raw["bars"][0], raw["bars"][1] = raw["bars"][1], raw["bars"][0]
    if "sequence" in mutation:
        raw["bars"][2]["source_sequence"] = mutation["sequence"]
    with pytest.raises(ValidationError, match=message):
        ReplayFixtureDocument.model_validate_json(json.dumps(raw))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("open", "3000"),
        ("close", "3000"),
        ("volume", "-1"),
        ("bar_timestamp", "2024-06-03T03:50:00"),
    ],
)
def test_invalid_ohlc_volume_and_naive_time_are_rejected(field: str, value: str) -> None:
    raw = json.loads(fixture_bytes())
    raw["bars"][1][field] = value
    with pytest.raises(ValidationError):
        ReplayFixtureDocument.model_validate_json(json.dumps(raw))


def test_malformed_manifest_is_rejected() -> None:
    raw = manifest().model_dump(mode="json")
    raw["bar_count"] = 0
    with pytest.raises(ValidationError):
        ReplayManifest.model_validate_json(json.dumps(raw))
