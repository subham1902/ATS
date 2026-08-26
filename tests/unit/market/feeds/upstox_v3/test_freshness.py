from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from ats.market.derivatives.providers.models import SourceFreshness
from ats.market.feeds.upstox_v3 import (
    FeedFreshnessBoard,
    KeyFreshnessLatch,
    NormalizedFeedUpdate,
    UpdateKind,
)

KEY = "NSE_FO|TEST_ONLY_TOKEN_1"
T0 = datetime(2026, 8, 24, 4, 0, tzinfo=UTC)


def update(*, exchange: datetime, received_at: datetime, ltp: int = 12550) -> NormalizedFeedUpdate:
    return NormalizedFeedUpdate(
        instrument_key=KEY,
        kind=UpdateKind.OPTION,
        received_at=received_at,
        exchange_timestamp=exchange,
        last_traded_price=Decimal(ltp),
    )


def latch() -> KeyFreshnessLatch:
    return KeyFreshnessLatch(instrument_key=KEY, stale_after_ms=1_000)


class TestStates:
    def test_unknown_before_any_data(self) -> None:
        assert latch().evaluate(T0) is SourceFreshness.UNKNOWN

    def test_fresh_within_window(self) -> None:
        subject = latch()
        subject.record(update(exchange=T0 - timedelta(milliseconds=50), received_at=T0))
        assert subject.evaluate(T0) is SourceFreshness.FRESH
        almost = T0 + timedelta(milliseconds=900)
        assert subject.evaluate(almost) is SourceFreshness.FRESH

    def test_stale_when_evidence_exceeds_window(self) -> None:
        subject = latch()
        subject.record(update(exchange=T0, received_at=T0))
        late = T0 + timedelta(seconds=2)
        assert subject.evaluate(late) is SourceFreshness.STALE

    def test_ancient_exchange_timestamp_is_stale_even_if_just_received(self) -> None:
        subject = latch()
        subject.record(
            update(exchange=T0 - timedelta(hours=6), received_at=T0)
        )
        assert subject.evaluate(T0) is SourceFreshness.STALE

    def test_future_exchange_timestamp_is_unsafe(self) -> None:
        subject = latch()
        subject.record(update(exchange=T0 + timedelta(minutes=5), received_at=T0))
        assert subject.evaluate(T0) is SourceFreshness.STALE

    def test_resync_required_overrides_everything(self) -> None:
        subject = latch()
        subject.record(update(exchange=T0, received_at=T0))
        subject.mark_resync_required()
        assert subject.evaluate(T0) is SourceFreshness.RESYNC_REQUIRED


class TestDuplicatesAndRegressions:
    def test_identical_duplicate_is_idempotent(self) -> None:
        subject = latch()
        first = update(exchange=T0, received_at=T0)
        second = update(exchange=T0, received_at=T0 + timedelta(milliseconds=10))
        assert subject.record(first).applied is True
        decision = subject.record(second)
        assert decision.duplicate is True
        assert decision.applied is False
        assert subject.last_update == first

    def test_out_of_order_timestamp_latches_resync(self) -> None:
        subject = latch()
        subject.record(update(exchange=T0 + timedelta(seconds=2), received_at=T0))
        decision = subject.record(
            update(exchange=T0 + timedelta(seconds=1), received_at=T0 + timedelta(seconds=1))
        )
        assert decision.regression is True
        assert subject.evaluate(T0 + timedelta(milliseconds=1)) is (
            SourceFreshness.RESYNC_REQUIRED
        )

    def test_equal_timestamp_with_changed_content_latches_resync(self) -> None:
        subject = latch()
        subject.record(update(exchange=T0 + timedelta(seconds=1), received_at=T0))
        decision = subject.record(
            update(exchange=T0 + timedelta(seconds=1), received_at=T0, ltp=999)
        )
        assert decision.regression is True

    def test_complete_resync_requires_recorded_evidence(self) -> None:
        subject = latch()
        with pytest.raises(ValueError):
            subject.complete_resync()

    def test_complete_resync_restores_eligibility(self) -> None:
        subject = latch()
        subject.record(update(exchange=T0 + timedelta(seconds=2), received_at=T0))
        subject.record(update(exchange=T0 + timedelta(seconds=1), received_at=T0))
        assert subject.evaluate(T0) is SourceFreshness.RESYNC_REQUIRED
        subject.record(update(exchange=T0 + timedelta(seconds=3), received_at=T0))
        subject.complete_resync()
        assert subject.evaluate(T0 + timedelta(seconds=30)) is SourceFreshness.STALE


class TestReconcile:
    def test_reconcile_clears_resync_only_on_genuinely_fresh_evidence(self) -> None:
        subject = latch()
        subject.mark_resync_required()
        state = subject.reconcile(
            update(exchange=T0 - timedelta(milliseconds=20), received_at=T0), now=T0
        )
        assert state is SourceFreshness.FRESH
        assert subject.evaluate(T0) is SourceFreshness.FRESH

    def test_reconcile_with_stale_snapshot_keeps_resync(self) -> None:
        subject = latch()
        subject.mark_resync_required()
        state = subject.reconcile(
            update(exchange=T0 - timedelta(hours=6), received_at=T0), now=T0
        )
        assert state is SourceFreshness.STALE
        assert subject.evaluate(T0) is SourceFreshness.RESYNC_REQUIRED

    def test_reconcile_with_regression_keeps_resync(self) -> None:
        subject = latch()
        subject.record(update(exchange=T0 + timedelta(seconds=5), received_at=T0))
        subject.mark_resync_required()
        state = subject.reconcile(update(exchange=T0, received_at=T0), now=T0)
        assert state is SourceFreshness.RESYNC_REQUIRED
        assert subject.evaluate(T0) is SourceFreshness.RESYNC_REQUIRED


class TestBoardAggregate:
    def test_aggregate_takes_most_severe_state(self) -> None:
        board = FeedFreshnessBoard()
        board.register(instrument_key="NSE_FO|A", stale_after_ms=60_000)
        board.register(instrument_key="NSE_FO|B", stale_after_ms=60_000)
        for key in ("NSE_FO|A", "NSE_FO|B"):
            board.latch(key).record(
                NormalizedFeedUpdate(
                    instrument_key=key,
                    kind=UpdateKind.INDEX,
                    received_at=T0,
                    exchange_timestamp=T0,
                )
            )
        board.latch("NSE_FO|B").mark_resync_required()
        per_key = board.evaluate(T0)
        assert per_key["NSE_FO|A"] is SourceFreshness.FRESH
        assert per_key["NSE_FO|B"] is SourceFreshness.RESYNC_REQUIRED
        assert board.aggregate(T0) is SourceFreshness.RESYNC_REQUIRED

    def test_empty_board_is_unknown(self) -> None:
        assert FeedFreshnessBoard().aggregate(T0) is SourceFreshness.UNKNOWN
