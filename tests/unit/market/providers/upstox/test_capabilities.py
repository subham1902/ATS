from __future__ import annotations

from datetime import UTC, datetime

import pytest
from ats.market.providers.upstox import (
    AccessClass,
    CapabilityStatus,
    EntitlementClass,
    RateLimitClass,
    RateLimitPolicy,
    ReadAttemptResult,
    ReadRateLimitExhausted,
    ReadRequestCoordinator,
    UpstoxCapability,
    capability_catalogue,
    response_provenance,
)


def test_capability_matrix_is_complete_and_unique() -> None:
    catalogue = capability_catalogue()
    assert set(catalogue) == set(UpstoxCapability)
    assert len(catalogue) == len(UpstoxCapability)


def test_account_reads_are_static_ip_and_out_of_a2_scope() -> None:
    catalogue = capability_catalogue()
    account = [
        item
        for item in catalogue.values()
        if item.access_class is AccessClass.ACCOUNT_READ_STATIC_IP
    ]
    assert account
    assert all(item.static_ip_required for item in account)
    assert all(item.runtime_status is CapabilityStatus.OUT_OF_SCOPE_FOR_A2 for item in account)


def test_real_order_capability_is_unadapted_and_forbidden() -> None:
    item = capability_catalogue()[UpstoxCapability.REAL_ORDER_PLACEMENT]
    assert item.access_class is AccessClass.FORBIDDEN_IN_A2
    assert item.runtime_status is CapabilityStatus.FORBIDDEN_IN_A2
    assert item.entitlement is EntitlementClass.FORBIDDEN
    assert item.adapter is None


def test_plus_is_explicit_and_not_conflated_with_static_ip() -> None:
    catalogue = capability_catalogue()
    plus = [
        item for item in catalogue.values() if item.entitlement is EntitlementClass.PLUS_OPTIONAL
    ]
    assert {item.capability for item in plus} == {
        UpstoxCapability.EXPIRED_INSTRUMENTS,
        UpstoxCapability.BACKTESTING_ANALYTICS,
        UpstoxCapability.WEBSOCKET_FEED,
    }
    assert all(not item.static_ip_required for item in plus)


def policy() -> RateLimitPolicy:
    return RateLimitPolicy(
        rate_limit_class=RateLimitClass.STANDARD_MARKET_DATA,
        maximum_attempts=3,
        timeout_ms=1000,
        base_backoff_ms=100,
        maximum_backoff_ms=500,
    )


def test_429_honours_bounded_retry_after_then_succeeds() -> None:
    waits: list[float] = []
    responses = iter(
        (ReadAttemptResult(status_code=429, retry_after_ms=250), ReadAttemptResult(status_code=200))
    )
    subject = ReadRequestCoordinator((policy(),), wait=waits.append)

    result = subject.execute_read(
        RateLimitClass.STANDARD_MARKET_DATA, lambda _timeout: next(responses)
    )

    assert result.status_code == 200
    assert waits == [0.25]


def test_retry_exhaustion_is_bounded_and_secret_safe() -> None:
    attempts = 0

    def unavailable(_timeout: int) -> ReadAttemptResult:
        nonlocal attempts
        attempts += 1
        return ReadAttemptResult(status_code=503)

    subject = ReadRequestCoordinator((policy(),), wait=lambda _delay: None)
    with pytest.raises(ReadRateLimitExhausted) as error:
        subject.execute_read(RateLimitClass.STANDARD_MARKET_DATA, unavailable)
    assert attempts == 3
    assert "credential" not in str(error.value).casefold()


def test_execution_class_can_never_use_read_retry_path() -> None:
    subject = ReadRequestCoordinator((policy(),), wait=lambda _delay: None)
    with pytest.raises(ValueError, match="cannot enter"):
        subject.execute_read(RateLimitClass.NEVER_CALL, lambda _timeout: ReadAttemptResult(200))


def test_response_provenance_hashes_exact_raw_bytes() -> None:
    first = response_provenance(
        endpoint_category="MARKET_QUOTE",
        retrieved_at=datetime(2026, 8, 27, tzinfo=UTC),
        source_as_of=None,
        raw_body=b'{"value":1}',
        entitlement_class=EntitlementClass.STANDARD,
        normalizer_version="upstox-quote-v1",
    )
    second = response_provenance(
        endpoint_category="MARKET_QUOTE",
        retrieved_at=datetime(2026, 8, 27, tzinfo=UTC),
        source_as_of=None,
        raw_body=b'{"value":2}',
        entitlement_class=EntitlementClass.STANDARD,
        normalizer_version="upstox-quote-v1",
    )
    assert first.raw_hash != second.raw_hash
