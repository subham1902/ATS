"""Bounded, read-only D10 market-open acceptance runner.

This program never imports an order API. It emits sanitized JSON evidence and
returns 3 when an active NSE session is required rather than weakening freshness.
"""

from __future__ import annotations

import argparse
import gzip
import json
import os
import statistics
import sys
import time
import urllib.request
import winreg
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import uuid4

from ats.contracts.common import SystemClock
from ats.market.data_acquisition.upstox_client import UpstoxReadOnlyClient
from ats.market.derivatives.acquisition import (
    UpstoxInstrumentShapePolicy,
    parse_upstox_bod_records,
)
from ats.market.derivatives.active_window import (
    ActiveWindowPolicy,
    MarketStateFreshness,
    build_active_option_window,
)
from ats.market.derivatives.contract_master import DerivativeUnderlying
from ats.market.derivatives.providers.models import SourceFreshness
from ats.market.derivatives.reference_authority import (
    InstrumentReferenceAuthority,
    provider_records_to_reference_contracts,
)
from ats.market.feeds.upstox_v3 import (
    BANKNIFTY_INDEX_FEED_KEY,
    NIFTY_INDEX_FEED_KEY,
    FeedFreshnessBoard,
    FeedMode,
    SubscriptionRegistry,
    UpstoxFeedAuthorization,
    UpstoxFeedConfiguration,
    UpstoxFeedLimits,
    UpstoxV3FeedAdapter,
    UpstoxV3FeedAuthorizer,
    UpstoxV3ProtobufDecoder,
    UpstoxV3Transport,
    WireFormat,
)
from pydantic import SecretStr

_NSE_BOD_URL = "https://assets.upstox.com/market-quote/instruments/exchange/NSE.json.gz"
_ALIASES = {
    "NIFTY": DerivativeUnderlying.NIFTY,
    "BANKNIFTY": DerivativeUnderlying.BANKNIFTY,
}


@dataclass(slots=True)
class _Metrics:
    receive_decode_normalize_ms: list[float]
    provider_age_ms: list[float]

    def report(self) -> dict[str, dict[str, float | int | None]]:
        return {
            "receive_decode_normalize": _percentiles(self.receive_decode_normalize_ms),
            "provider_age": _percentiles(self.provider_age_ms),
        }


class _LatestSnapshot:
    def __init__(self, adapter: UpstoxV3FeedAdapter) -> None:
        self._adapter = adapter

    def full_snapshot(self, instrument_keys: tuple[str, ...]):
        updates = tuple(self._adapter.latest(key) for key in instrument_keys)
        return tuple(item for item in updates if item is not None)


def _load_token() -> SecretStr | None:
    value = os.environ.get("ATS_UPSTOX_ACCESS_TOKEN")
    if not value:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
                candidate = winreg.QueryValueEx(key, "ATS_UPSTOX_ACCESS_TOKEN")[0]
                value = candidate if isinstance(candidate, str) else None
        except OSError:
            value = None
    return SecretStr(value) if value else None


def _fetch_reference(now: datetime):
    request = urllib.request.Request(
        _NSE_BOD_URL, headers={"Accept": "application/gzip", "User-Agent": "ATS-D10-Acceptance/1.0"}
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        compressed = response.read()
    raw = gzip.decompress(compressed)
    records = parse_upstox_bod_records(
        raw,
        source_as_of=now,
        policy=UpstoxInstrumentShapePolicy(
            schema_version="1.0",
            strike_price_scale=Decimal("1"),
            tick_size_scale=Decimal("0.01"),
            tradable_default=True,
        ),
    )
    contracts = provider_records_to_reference_contracts(records, underlying_aliases=_ALIASES)
    return contracts


def _extract_ltp(document: dict[str, Any], instrument_key: str) -> Decimal:
    data = document.get("data")
    if not isinstance(data, dict):
        raise ValueError("MARKET_QUOTE_SHAPE_INVALID")
    candidates = [data.get(instrument_key), *data.values()]
    for item in candidates:
        if not isinstance(item, dict):
            continue
        value = item.get("last_price", item.get("ltp"))
        if isinstance(value, int | float | Decimal) and not isinstance(value, bool):
            price = Decimal(str(value))
            if price > 0:
                return price
    raise ValueError("MARKET_QUOTE_LTP_MISSING")


def _classify_session_evidence(
    freshness: Mapping[str, SourceFreshness], market_status: Mapping[str, str]
) -> tuple[dict[str, object], int] | None:
    """Return a deferral for non-active evidence, otherwise allow FRESH checks to continue."""
    provider_active = bool(freshness) and all(
        value is SourceFreshness.FRESH for value in freshness.values()
    )
    market_open = not market_status or any("OPEN" in status for status in market_status.values())
    if provider_active and market_open:
        return None
    return {
        "status": "ACTIVE_MARKET_SESSION_REQUIRED_FOR_D10_ACCEPTANCE",
        "market_status": dict(market_status),
        "freshness": {key: value.value for key, value in freshness.items()},
        "real_orders_placed": 0,
    }, 3


def _failure_evidence(error: Exception) -> tuple[dict[str, object], int]:
    return {
        "status": "D10_LIVE_ACCEPTANCE_FAILED",
        "error_type": type(error).__name__,
        "real_orders_placed": 0,
    }, 2


def _build_windows(contracts, quote_client: UpstoxReadOnlyClient, now: datetime):
    windows = {}
    for underlying, key in (
        (DerivativeUnderlying.NIFTY, NIFTY_INDEX_FEED_KEY),
        (DerivativeUnderlying.BANKNIFTY, BANKNIFTY_INDEX_FEED_KEY),
    ):
        price = _extract_ltp(quote_client.ltp(key), key)
        expiries = sorted(
            {
                item.expiry
                for item in contracts
                if item.underlying is underlying
                and item.option_type is not None
                and item.expiry >= now.date().isoformat()
            }
        )
        if not expiries:
            raise ValueError(f"{underlying.value}_CURRENT_EXPIRY_MISSING")
        windows[underlying] = build_active_option_window(
            contracts=contracts,
            underlying=underlying,
            underlying_price=price,
            as_of_time=now,
            policy=ActiveWindowPolicy(
                window_size=2,
                expiry=expiries[0],
                maximum_master_age_ms=60_000,
                maximum_quote_age_ms=10_000,
            ),
        )
    return windows


def _receive_until_complete(
    transport: UpstoxV3Transport,
    adapter: UpstoxV3FeedAdapter,
    keys: tuple[str, ...],
    metrics: _Metrics,
    *,
    timeout_seconds: float,
) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        started = time.perf_counter_ns()
        payload = transport.receive()
        received = datetime.now(UTC)
        adapter.handle_frame(payload, received_at=received)
        metrics.receive_decode_normalize_ms.append((time.perf_counter_ns() - started) / 1_000_000)
        for key in keys:
            update = adapter.latest(key)
            if update is not None and update.exchange_timestamp is not None:
                metrics.provider_age_ms.append(
                    max(0.0, (received - update.exchange_timestamp).total_seconds() * 1000)
                )
        if all(adapter.latest(key) is not None for key in keys):
            return
    raise TimeoutError("BOUNDED_FEED_EVIDENCE_TIMEOUT")


def _window_evidence(window, authority: InstrumentReferenceAuthority, now: datetime, adapter):
    keys = tuple(
        key
        for pair in window.pairs
        for key in (pair.ce_provider_instrument_key, pair.pe_provider_instrument_key)
    )
    specs = [authority.resolve(key, as_of=now) for key in keys]
    updates = [adapter.latest(key) for key in keys]
    return {
        "underlying_price": str(window.underlying_price),
        "expiry": window.expiry,
        "atm_strike": str(window.atm_strike),
        "strikes": [str(pair.strike) for pair in window.pairs],
        "contract_count": len(keys),
        "contracts": [
            {
                "instrument_key": spec.instrument_key,
                "lot_size": spec.lot_size,
                "tick_size": str(spec.tick_size),
                "freshness": (
                    MarketStateFreshness.FRESH.value
                    if update is not None and update.exchange_timestamp is not None
                    else MarketStateFreshness.UNKNOWN.value
                ),
                "ltp": str(update.last_traded_price)
                if update and update.last_traded_price
                else None,
                "bid": str(update.bid_price) if update and update.bid_price else None,
                "ask": str(update.ask_price) if update and update.ask_price else None,
                "depth_levels": (
                    len(update.market_depth.buy_levels) + len(update.market_depth.sell_levels)
                    if update and update.market_depth
                    else 0
                ),
                "volume": update.volume if update else None,
                "oi": update.open_interest if update else None,
                "iv": update.implied_volatility if update else None,
                "delta": update.delta if update else None,
                "gamma": update.gamma if update else None,
                "theta": update.theta if update else None,
                "vega": update.vega if update else None,
                "rho": update.rho if update else None,
                "provider_timestamp": (
                    update.exchange_timestamp.isoformat()
                    if update and update.exchange_timestamp
                    else None
                ),
                "receive_timestamp": update.received_at.isoformat() if update else None,
            }
            for spec, update in zip(specs, updates, strict=True)
        ],
    }


def run_live(timeout_seconds: float) -> tuple[dict[str, object], int]:
    token = _load_token()
    if token is None:
        return {
            "status": "TOKEN_NOT_CONFIGURED",
            "token_presence": "ABSENT",
            "real_orders_placed": 0,
        }, 2
    now = datetime.now(UTC)
    contracts = _fetch_reference(now)
    quote_client = UpstoxReadOnlyClient(token=token.get_secret_value())
    windows = _build_windows(contracts, quote_client, now)
    option_keys = tuple(
        key
        for window in windows.values()
        for pair in window.pairs
        for key in (pair.ce_provider_instrument_key, pair.pe_provider_instrument_key)
    )
    keys = (NIFTY_INDEX_FEED_KEY, BANKNIFTY_INDEX_FEED_KEY, *option_keys)
    registry = SubscriptionRegistry()
    board = FeedFreshnessBoard()
    for key in keys:
        registry.register(instrument_key=key, ats_identity=key, mode=FeedMode.FULL)
        board.register(instrument_key=key, stale_after_ms=10_000)
    configuration = UpstoxFeedConfiguration(
        wire_format=WireFormat.PROTOBUF_BINARY,
        client_guid=str(uuid4()),
        limits=UpstoxFeedLimits(
            maximum_silence_ms=5_000,
            stale_after_ms=10_000,
            maximum_buffered_frames=32,
            receive_timeout_ms=5_000,
        ),
    )
    authorization = UpstoxFeedAuthorization(bearer_token=token)
    authorizer = UpstoxV3FeedAuthorizer(authorization)
    transport = UpstoxV3Transport(configuration=configuration, authorizer=authorizer)
    decoder = UpstoxV3ProtobufDecoder()
    adapter = UpstoxV3FeedAdapter(
        configuration=configuration,
        authorization=authorization,
        registry=registry,
        freshness_board=board,
        decoder=decoder,
        clock=SystemClock(),
    )
    metrics = _Metrics([], [])
    try:
        connection = transport.connect()
        adapter.connect(connection)
        _receive_until_complete(transport, adapter, keys, metrics, timeout_seconds=timeout_seconds)
        evidence_time = datetime.now(UTC)
        initial_freshness = board.evaluate(evidence_time)
        session_outcome = _classify_session_evidence(
            initial_freshness, decoder.last_market_status
        )
        if session_outcome is not None:
            evidence, code = session_outcome
            evidence["token_presence"] = "PRESENT"
            return evidence, code
        adapter.disconnect()
        resync_state = adapter.state.value
        transport.close()
        connection = transport.connect()
        adapter.reconnect(connection)
        _receive_until_complete(transport, adapter, keys, metrics, timeout_seconds=timeout_seconds)
        adapter.complete_resync(_LatestSnapshot(adapter), now=datetime.now(UTC))
        final_time = datetime.now(UTC)
        final_freshness = board.evaluate(final_time)
        authority = InstrumentReferenceAuthority(
            contracts=contracts, retrieved_at=now, maximum_age=timedelta(hours=6)
        )
        return {
            "status": "D10_LIVE_ACCEPTANCE_PASS",
            "authority_scope": "READ_ONLY_MARKET_DATA",
            "token_presence": "PRESENT",
            "market_status": decoder.last_market_status,
            "provider_current_timestamp": (
                decoder.last_current_timestamp.isoformat()
                if decoder.last_current_timestamp
                else None
            ),
            "subscriptions": len(keys),
            "nifty": _window_evidence(
                windows[DerivativeUnderlying.NIFTY], authority, final_time, adapter
            ),
            "banknifty": _window_evidence(
                windows[DerivativeUnderlying.BANKNIFTY], authority, final_time, adapter
            ),
            "disconnect_state": resync_state,
            "reconnect_freshness": {key: value.value for key, value in final_freshness.items()},
            "queue": {
                "configured_max_frames": configuration.limits.maximum_buffered_frames,
                "frames_handled": adapter.diagnostics.frames_handled,
                "duplicates": adapter.diagnostics.duplicate_updates,
                "regressions": adapter.diagnostics.regression_updates,
            },
            "latency_ms": metrics.report(),
            "real_orders_placed": 0,
        }, 0
    finally:
        adapter.disconnect()
        transport.close()


def _percentiles(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {"count": 0, "p50": None, "p95": None, "p99": None, "max": None}
    ordered = sorted(values)

    def pick(fraction: float) -> float:
        return ordered[min(len(ordered) - 1, int((len(ordered) - 1) * fraction))]

    return {
        "count": len(ordered),
        "p50": round(statistics.median(ordered), 6),
        "p95": round(pick(0.95), 6),
        "p99": round(pick(0.99), 6),
        "max": round(max(ordered), 6),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    args = parser.parse_args()
    if not args.live:
        print(json.dumps({"status": "DRY_RUN_PASS", "real_orders_placed": 0}, sort_keys=True))
        return 0
    try:
        evidence, code = run_live(args.timeout_seconds)
    except Exception as error:
        evidence, code = _failure_evidence(error)
    print(json.dumps(evidence, sort_keys=True, separators=(",", ":")))
    return code


if __name__ == "__main__":
    sys.exit(main())
