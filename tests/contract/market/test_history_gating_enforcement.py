"""Leakage enforcement: no strategy-facing code may bypass the history gate."""

from __future__ import annotations

import inspect
import re
from pathlib import Path

from ats.market.fixtures import create_approved_replay
from ats.market.fixtures.loader import _load_approved_fixture
from ats.market.history import HistoricalReplaySession

_ALLOWED_PREFIXES = (
    "market/replay",
    "market/history",
    "market/fixtures",
)

_CONSTRUCTOR_PATTERN = re.compile(r"DeterministicReplay\s*\(")
_DEEP_IMPORT_TOKEN = "ats.market.replay.engine"


def _production_sources() -> list[Path]:
    root = Path("backend/src/ats")
    sources: list[Path] = []
    for source in sorted(root.rglob("*.py")):
        posix = source.relative_to(root).as_posix()
        if any(posix.startswith(prefix) for prefix in _ALLOWED_PREFIXES):
            continue
        sources.append(source)
    return sources


def test_no_production_module_constructs_raw_replay() -> None:
    offenders: list[str] = []
    for source in _production_sources():
        text = source.read_text(encoding="utf-8")
        if _CONSTRUCTOR_PATTERN.search(text):
            offenders.append(str(source))
    assert offenders == [], (
        "raw DeterministicReplay construction outside the history gate: " + ", ".join(offenders)
    )


def test_no_production_module_deep_imports_replay_engine() -> None:
    offenders: list[str] = []
    for source in _production_sources():
        text = source.read_text(encoding="utf-8")
        if _DEEP_IMPORT_TOKEN in text:
            offenders.append(str(source))
    assert offenders == [], "deep replay-engine imports outside the history gate: " + ", ".join(
        offenders
    )


def test_approved_fixture_loader_returns_history_gated_session() -> None:
    signature = inspect.signature(create_approved_replay)
    assert signature.return_annotation in ("HistoricalReplaySession", HistoricalReplaySession)


def test_gated_session_hides_future_bars_and_records_ledger() -> None:
    from ats.market import (
        ApprovedFixture,
        ReplayConfiguration,
        approved_manifest,
        nse_cash_alpha_v1_calendar,
    )

    calendar = nse_cash_alpha_v1_calendar()
    dataset = _load_approved_fixture(ApprovedFixture.NSE_CASH_RELIANCE_5M_V1, calendar)
    manifest = approved_manifest(ApprovedFixture.NSE_CASH_RELIANCE_5M_V1)
    session = create_approved_replay(
        ApprovedFixture.NSE_CASH_RELIANCE_5M_V1,
        calendar,
        ReplayConfiguration(start_at=manifest.first_bar, received_delay_ms=250),
    )
    assert isinstance(session, HistoricalReplaySession)
    first = session.advance()
    gated_bars = [
        item for item in session.visible_observations() if item.kind.value == "MARKET_BAR"
    ]
    assert len(gated_bars) == 1
    assert gated_bars[0].times.event_time == first.bar_timestamp
    assert session.attribution_ledger()[0].visible_count == len(gated_bars)
    remaining = len(dataset.bars) - 1
    for _ in range(remaining):
        session.advance()
    all_bars = [item for item in session.visible_observations() if item.kind.value == "MARKET_BAR"]
    assert len(all_bars) == len(dataset.bars)
