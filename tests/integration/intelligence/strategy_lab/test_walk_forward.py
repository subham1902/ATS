from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from ats.contracts.domain.types import DataQualityState, SessionState
from ats.market.replay.models import ReplayBar, ReplayDataset, ReplayManifest
from ats.intelligence.strategy_lab.walk_forward import build_rolling_plan


def _bars(n: int = 30) -> ReplayDataset:
    base = datetime(2024, 1, 1, tzinfo=UTC)
    bars = []
    for i in range(n):
        bars.append(
            ReplayBar(
                instrument_id="NSE_EQ-TCS",
                exchange="NSE",
                segment="CASH",
                timeframe="5m",
                bar_timestamp=base + timedelta(minutes=5 * i),
                open=Decimal("100"),
                high=Decimal("101"),
                low=Decimal("99"),
                close=Decimal("100"),
                volume=Decimal("1000"),
                source_sequence=i + 1,
                quality_state=DataQualityState.GOOD,
                quality_flags=(),
                session_state=SessionState.OPEN,
            )
        )
    manifest = ReplayManifest(
        dataset_id=uuid4(),
        dataset_version="v1",
        source_description="test",
        instrument="NSE_EQ-TCS",
        exchange="NSE",
        segment="CASH",
        timeframe="5m",
        first_bar=bars[0].bar_timestamp,
        last_bar=bars[-1].bar_timestamp,
        bar_count=len(bars),
        content_sha256="a" * 64,
        calendar_id="XNSE",
        calendar_version="1",
    )
    return ReplayDataset(manifest=manifest, bars=tuple(bars))


def test_walk_forward_no_leakage() -> None:
    dataset = _bars(30)
    plan = build_rolling_plan(dataset=dataset, train_bars=10, test_bars=5, purge_bars=1, embargo_bars=1)
    assert len(plan.windows) > 0
    # Chronology
    for i in range(1, len(plan.windows)):
        prev = plan.windows[i - 1]
        cur = plan.windows[i]
        assert cur.test_start > prev.test_end  # type: ignore[operator]


def test_walk_forward_purge_embargo() -> None:
    dataset = _bars(20)
    plan = build_rolling_plan(dataset=dataset, train_bars=5, test_bars=5, purge_bars=2, embargo_bars=2)
    w = plan.windows[0]
    assert w.purge_bars == 2
    assert w.embargo_bars == 2
