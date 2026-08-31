from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from ats.market.derivatives.providers.models import SourceFreshness
from ats.market.feeds.upstox_v3 import (
    FeedMode,
    NormalizedFeedUpdate,
    UpdateKind,
    UpstoxFeedError,
    UpstoxFeedErrorCode,
    UpstoxV3FeedAdapter,
    build_handshake_headers,
    subscribe_frame,
)
from ats.market.feeds.upstox_v3.adapter import ConnectionState

from . import helpers as fix


def adapter(*, with_token: bool = True):
    clock = fix.FakeClock()
    subject = UpstoxV3FeedAdapter(
        configuration=fix.configuration(),
        authorization=fix.authorization(with_token=with_token),
        registry=fix.registry(),
        freshness_board=fix.freshness_board(),
        decoder=fix.decoder(),
        clock=clock,
    )
    return subject, clock


def connected():
    subject, clock = adapter()
    connection = fix.RecordingConnection()
    subject.connect(connection)
    return subject, clock, connection


class StubReconciliation:
    def __init__(self, updates: tuple[NormalizedFeedUpdate, ...]) -> None:
        self._updates = updates

    def full_snapshot(self, instrument_keys):  # type: ignore[no-untyped-def]
        return self._updates


class TestAuthorization:
    def test_connect_without_injected_token_fails_closed(self) -> None:
        subject, _ = adapter(with_token=False)
        with pytest.raises(UpstoxFeedError) as error:
            subject.connect(fix.RecordingConnection())
        assert error.value.code is UpstoxFeedErrorCode.AUTHORIZATION_REQUIRED

    def test_handshake_headers_unwrap_token_exactly_once(self) -> None:
        headers = build_handshake_headers(fix.authorization())
        assert headers == {"Authorization": f"Bearer {fix.TEST_ONLY_SECRET}"}

    def test_error_text_never_carries_the_secret(self) -> None:
        subject, _ = adapter(with_token=False)
        with pytest.raises(UpstoxFeedError) as error:
            subject.connect(fix.RecordingConnection())
        assert fix.TEST_ONLY_SECRET not in str(error.value)


class TestConnectAndSubscribe:
    def test_connect_sends_full_subscription_from_registry(self) -> None:
        subject, _, connection = connected()
        assert subject.state is ConnectionState.LIVE
        expected = (
            subscribe_frame(
                guid="d08-test-guid",
                mode=FeedMode.FULL,
                instrument_keys=(fix.INDEX_KEY,),
            ),
            subscribe_frame(
                guid="d08-test-guid",
                mode=FeedMode.LTPC,
                instrument_keys=(fix.SECOND_OPTION_KEY,),
            ),
            subscribe_frame(
                guid="d08-test-guid",
                mode=FeedMode.OPTION_GREEKS,
                instrument_keys=(fix.OPTION_KEY,),
            ),
        )
        assert tuple(connection.sent) == expected

    def test_double_connect_is_refused(self) -> None:
        subject, _, _ = connected()
        with pytest.raises(UpstoxFeedError) as error:
            subject.connect(fix.RecordingConnection())
        assert error.value.code is UpstoxFeedErrorCode.ALREADY_CONNECTED


class TestFrameHandling:
    def test_partial_coverage_keeps_aggregate_unknown_until_every_key_is_alive(self) -> None:
        subject, clock, _ = connected()
        stamp = clock.advance(milliseconds=10)
        base_ts = int(stamp.timestamp() * 1000)
        outcome = subject.handle_frame(
            fix.ltpc_frame(
                instrument_key=fix.INDEX_KEY,
                ltp=2500150,
                cp=2495000,
                ltt_ms=base_ts - 50,
                ts_ms=base_ts,
            ),
            received_at=stamp,
        )
        assert outcome.applied_updates == (fix.INDEX_KEY,)
        latest = subject.latest(fix.INDEX_KEY)
        assert latest is not None
        assert latest.last_traded_price == Decimal("25001.50")
        # one alive key cannot make the whole subscription set safe
        assert subject.evaluate_freshness(now=stamp) is SourceFreshness.UNKNOWN

    def test_all_keys_alive_within_window_reads_fresh(self) -> None:
        subject, clock, _ = connected()
        stamp = clock.advance(milliseconds=10)
        base_ts = int(stamp.timestamp() * 1000)
        for key, ltp in (
            (fix.INDEX_KEY, 2500150),
            (fix.OPTION_KEY, 12550),
            (fix.SECOND_OPTION_KEY, 9900),
        ):
            subject.handle_frame(
                fix.ltpc_frame(instrument_key=key, ltp=ltp, cp=ltp, ltt_ms=base_ts, ts_ms=base_ts),
                received_at=stamp,
            )
        assert subject.evaluate_freshness(now=stamp) is SourceFreshness.FRESH

    def test_unknown_instrument_is_quarantined_not_fatal(self) -> None:
        subject, clock, _ = connected()
        stamp = clock.advance(milliseconds=5)
        outcome = subject.handle_frame(
            fix.ltpc_frame(instrument_key=fix.UNKNOWN_KEY, ltp=1, cp=1, ltt_ms=0, ts_ms=0),
            received_at=stamp,
        )
        assert outcome.unknown_keys == (fix.UNKNOWN_KEY,)
        assert subject.diagnostics.unknown_updates == 1
        assert subject.latest(fix.UNKNOWN_KEY) is None
        assert subject.state is ConnectionState.LIVE

    def test_malformed_frame_counts_and_raises(self) -> None:
        subject, clock, _ = connected()
        stamp = clock.advance(milliseconds=5)
        with pytest.raises(UpstoxFeedError):
            subject.handle_frame("::garbage::", received_at=stamp)
        assert subject.diagnostics.malformed_frames == 1
        assert subject.state is ConnectionState.LIVE

    def test_duplicate_message_is_idempotent(self) -> None:
        subject, clock, _ = connected()
        first = clock.advance(milliseconds=5)
        second = clock.advance(milliseconds=5)
        frame = fix.ltpc_frame(
            instrument_key=fix.OPTION_KEY,
            ltp=12550,
            cp=10000,
            ltt_ms=1771000000000,
            ts_ms=1771000000000,
        )
        subject.handle_frame(frame, received_at=first)
        outcome = subject.handle_frame(frame, received_at=second)
        assert outcome.duplicate_keys == (fix.OPTION_KEY,)
        assert subject.diagnostics.duplicate_updates == 1

    def test_out_of_order_timestamp_latches_resync(self) -> None:
        subject, clock, _ = connected()
        first = clock.advance(milliseconds=5)
        second = clock.advance(milliseconds=5)
        subject.handle_frame(
            fix.ltpc_frame(
                instrument_key=fix.OPTION_KEY,
                ltp=12600,
                cp=10000,
                ltt_ms=1771000015000,
                ts_ms=1771000015000,
            ),
            received_at=first,
        )
        outcome = subject.handle_frame(
            fix.ltpc_frame(
                instrument_key=fix.OPTION_KEY,
                ltp=12500,
                cp=10000,
                ltt_ms=1771000014000,
                ts_ms=1771000014000,
            ),
            received_at=second,
        )
        assert outcome.regression_keys == (fix.OPTION_KEY,)
        assert subject.evaluate_freshness() is SourceFreshness.RESYNC_REQUIRED

    def test_frame_before_connect_is_refused(self) -> None:
        subject, _ = adapter()
        with pytest.raises(UpstoxFeedError) as error:
            subject.handle_frame("{}")
        assert error.value.code is UpstoxFeedErrorCode.NOT_CONNECTED


class TestSilenceAndStaleness:
    def test_silence_beyond_limit_reads_stale_never_fresh(self) -> None:
        subject, clock, connection = connected()
        stamp = clock.advance(milliseconds=5)
        base_ts = int(stamp.timestamp() * 1000)
        for key in (fix.INDEX_KEY, fix.OPTION_KEY, fix.SECOND_OPTION_KEY):
            subject.handle_frame(
                fix.ltpc_frame(instrument_key=key, ltp=100, cp=90, ltt_ms=base_ts, ts_ms=base_ts),
                received_at=stamp,
            )
        quiet = clock.advance(milliseconds=2_000)
        assert subject.evaluate_freshness(now=quiet) is SourceFreshness.STALE
        assert connection.closed is False

    def test_no_data_at_all_is_unknown(self) -> None:
        subject, clock, _ = connected()
        assert subject.evaluate_freshness(now=clock.now()) is SourceFreshness.UNKNOWN


class TestDisconnectReconnectResync:
    def test_disconnect_marks_every_latch_resync_required(self) -> None:
        subject, clock, _ = connected()
        stamp = clock.advance(milliseconds=5)
        subject.handle_frame(
            fix.ltpc_frame(instrument_key=fix.INDEX_KEY, ltp=2500100, cp=1, ltt_ms=0, ts_ms=0),
            received_at=stamp,
        )
        subject.disconnect()
        assert subject.state is ConnectionState.RESYNC_REQUIRED
        assert subject.evaluate_freshness(now=clock.now()) is SourceFreshness.RESYNC_REQUIRED

    def test_reconnect_performs_full_resubscription_and_stays_unsafe(self) -> None:
        subject, _, first_connection = connected()
        subject.disconnect()
        reconnection = fix.RecordingConnection()
        subject.reconnect(reconnection)
        assert subject.state is ConnectionState.RESYNC_REQUIRED
        assert len(reconnection.sent) == len(first_connection.sent)
        assert sorted(reconnection.sent) == sorted(first_connection.sent)

    def test_complete_resync_requires_full_key_coverage(self) -> None:
        subject, clock, _ = connected()
        subject.disconnect()
        reconciliation = StubReconciliation(())
        with pytest.raises(UpstoxFeedError) as error:
            subject.complete_resync(reconciliation, now=clock.now())
        assert error.value.code is UpstoxFeedErrorCode.RECONCILIATION_GAP
        assert subject.state is ConnectionState.RESYNC_REQUIRED

    def test_complete_resync_restores_fresh_state(self) -> None:
        subject, clock, _ = connected()
        subject.disconnect()
        stamp = clock.now()
        exchange = stamp - timedelta(seconds=1)

        def snapshot(keys):  # type: ignore[no-untyped-def]
            return tuple(
                NormalizedFeedUpdate(
                    instrument_key=key,
                    kind=UpdateKind.INDEX if key.startswith("NSE_INDEX|") else UpdateKind.OPTION,
                    received_at=stamp,
                    exchange_timestamp=exchange,
                    last_traded_price=Decimal("101"),
                )
                for key in keys
            )

        subject.complete_resync(StubReconciliation(snapshot(subject_keys())), now=stamp)
        assert subject.state is ConnectionState.LIVE
        assert subject.diagnostics.reconciliations_completed == 1
        assert subject.evaluate_freshness(now=stamp + timedelta(milliseconds=100)) is (
            SourceFreshness.FRESH
        )

    def test_reconciled_stale_snapshot_refuses_completion(self) -> None:
        subject, clock, _ = connected()
        subject.disconnect()
        stamp = clock.now()
        old_exchange = datetime.fromtimestamp(1771000000000 / 1000, tz=UTC) - timedelta(hours=6)

        def snapshot(keys):  # type: ignore[no-untyped-def]
            return tuple(
                NormalizedFeedUpdate(
                    instrument_key=key,
                    kind=UpdateKind.OPTION,
                    received_at=stamp,
                    exchange_timestamp=old_exchange,
                )
                for key in keys
            )

        with pytest.raises(UpstoxFeedError) as error:
            subject.complete_resync(StubReconciliation(snapshot(subject_keys())), now=stamp)
        assert error.value.code is UpstoxFeedErrorCode.RESYNC_INCOMPLETE
        assert subject.state is ConnectionState.RESYNC_REQUIRED


def subject_keys() -> tuple[str, ...]:
    return fix.registry().instrument_keys()
