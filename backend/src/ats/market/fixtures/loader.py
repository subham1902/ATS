"""Integrity-first fixture loading with no downloader or arbitrary path API."""

from __future__ import annotations

import hashlib
from importlib.resources import files

from ats.contracts.enums import ATSStringEnum
from ats.market.calendar import SessionCalendar
from ats.market.history import HistoricalReplaySession
from ats.market.history.replay_bridge import create_history_gated_replay
from ats.market.replay.models import (
    ReplayConfiguration,
    ReplayDataset,
    ReplayFixtureDocument,
    ReplayManifest,
)


class ApprovedFixture(ATSStringEnum):
    NSE_CASH_RELIANCE_5M_V1 = "NSE_CASH_RELIANCE_5M_V1"


_APPROVED_FILES = {
    ApprovedFixture.NSE_CASH_RELIANCE_5M_V1: (
        "nse_cash_reliance_5m_v1.manifest.json",
        "nse_cash_reliance_5m_v1.bars.json",
    )
}


def _load_replay_dataset(
    manifest: ReplayManifest,
    content: bytes,
    calendar: SessionCalendar,
) -> ReplayDataset:
    actual_hash = hashlib.sha256(content).hexdigest()
    if actual_hash != manifest.content_sha256:
        raise ValueError("fixture content SHA-256 does not match manifest")
    document = ReplayFixtureDocument.model_validate_json(content)
    if (
        document.dataset_id != manifest.dataset_id
        or document.dataset_version != manifest.dataset_version
    ):
        raise ValueError("fixture dataset identity does not match manifest")
    if (
        document.calendar_id != manifest.calendar_id
        or document.calendar_version != manifest.calendar_version
        or calendar.calendar_id != manifest.calendar_id
        or calendar.calendar_version != manifest.calendar_version
    ):
        raise ValueError("fixture calendar identity does not match manifest")
    for bar in document.bars:
        calendar.validate_bar_close(bar.bar_timestamp, bar.session_state)
    return ReplayDataset(manifest=manifest, bars=document.bars)


def approved_manifest(fixture: ApprovedFixture) -> ReplayManifest:
    manifest_name, _ = _APPROVED_FILES[fixture]
    package = files("ats.market.fixtures")
    return ReplayManifest.model_validate_json(package.joinpath(manifest_name).read_bytes())


def _load_approved_fixture(
    fixture: ApprovedFixture,
    calendar: SessionCalendar,
) -> ReplayDataset:
    _, fixture_name = _APPROVED_FILES[fixture]
    package = files("ats.market.fixtures")
    manifest = approved_manifest(fixture)
    return _load_replay_dataset(
        manifest,
        package.joinpath(fixture_name).read_bytes(),
        calendar,
    )


def create_approved_replay(
    fixture: ApprovedFixture,
    calendar: SessionCalendar,
    configuration: ReplayConfiguration,
) -> HistoricalReplaySession:
    """Construct a history-gated replay over an approved fixture.

    The returned session enforces the AS_OF_INFORMATION_MODEL on every
    advance: strategies can only observe bars whose availability time has
    passed, and each decision instant is recorded with a visible-window
    digest for attribution. Raw cursor replay remains available exclusively
    inside the historical-truth bridge, never to strategy-facing callers.
    """

    return create_history_gated_replay(
        _load_approved_fixture(fixture, calendar),
        configuration,
    )


__all__ = ["ApprovedFixture", "approved_manifest", "create_approved_replay"]
