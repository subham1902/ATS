"""Observed XAUUSD values only; terminal health controls every live claim."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from ats.market.domain import UnsupportedInstrument, classify_session, require_xauusd
from ats.market.fabric import BarInterval, MarketDataFabric
from ats.market.metatrader.connector import MetaTraderConnector

router = APIRouter(prefix="/v1/market", tags=["XAUUSD"])


def market_connection(request: Request) -> tuple[MetaTraderConnector, MarketDataFabric]:
    from ats.console.accounts_router import service_of

    service = service_of(request)
    try:
        result = service.market_connection(request.query_params.get("account_id"))
    except KeyError:
        raise HTTPException(404, "ACCOUNT_NOT_FOUND") from None
    except ValueError:
        raise HTTPException(409, "MARKET_ACCOUNT_SELECTION_OR_CONNECTION_REQUIRED") from None
    if result is not None:
        return result
    return request.app.state.metatrader_connector, request.app.state.market_fabric


def fabric_of(request: Request) -> MarketDataFabric:
    return market_connection(request)[1]


def require_instrument(instrument: str | None) -> str:
    try:
        return require_xauusd(instrument or "XAUUSD")
    except UnsupportedInstrument as error:
        raise HTTPException(422, str(error)) from error


@router.get("/health")
def get_market_health(request: Request) -> dict[str, Any]:
    terminal = market_connection(request)[0]
    health = terminal.health()
    counters = fabric_of(request).counters()
    return {
        **health,
        "provider_state": health["state"],
        "attached": health["state"] not in {"DISCONNECTED", "ERROR"},
        "source": terminal.domain.provider,
        "authority_class": "BROKER_TICK_PROXY",
        "instruments": ["XAUUSD"],
        "last_update_at": health["last_tick_timestamp"],
        "last_update_age_ms": health["feed_age_seconds"] * 1000
        if health["feed_age_seconds"] is not None
        else None,
        "stale_after_ms": terminal.domain.stale_after_seconds * 1000,
        "accepted_updates": counters.accepted,
        "dropped_duplicate": counters.dropped_duplicate,
        "dropped_out_of_order": counters.dropped_out_of_order,
        "dropped_stale": counters.dropped_stale,
        "subscriber_count": fabric_of(request).subscriber_count(),
        "reason_codes": [health["reason"]],
    }


@router.get("/quote")
@router.get("/snapshot")
def get_market_quote(request: Request, instrument: str | None = None) -> dict[str, Any]:
    require_instrument(instrument)
    tick = fabric_of(request).latest("XAUUSD")
    health = get_market_health(request)
    return {
        "instrument_key": "XAUUSD",
        "canonical_symbol": "XAUUSD",
        "broker_symbol": health["source_symbol"],
        "state": health["state"],
        "connection_state": health["state"],
        "source": health["source"],
        "provider": health["source"],
        "authority_class": "BROKER_TICK_PROXY",
        "provenance": tick.provenance if tick else "UNKNOWN",
        "last_price": str(tick.last) if tick and tick.last is not None else None,
        "bid_price": str(tick.bid) if tick and tick.bid is not None else None,
        "ask_price": str(tick.ask) if tick and tick.ask is not None else None,
        "spread": health["spread"],
        "volume": str(tick.volume) if tick and tick.volume is not None else None,
        "tick_volume": str(tick.tick_volume) if tick and tick.tick_volume is not None else None,
        "real_volume": str(tick.real_volume) if tick and tick.real_volume is not None else None,
        "volume_provenance": tick.volume_provenance.value if tick else "UNKNOWN",
        "bid_quantity": None,
        "ask_quantity": None,
        "open_interest": None,
        "exchange_timestamp": tick.timestamp.isoformat() if tick else None,
        "received_at": tick.received_at.isoformat() if tick else None,
        "age_ms": health["last_update_age_ms"],
        "freshness_ms": health["last_update_age_ms"],
        "market_session": ", ".join(classify_session(datetime.now(UTC))),
        "reason_codes": health["reason_codes"],
    }


@router.get("/candles")
def get_market_candles(
    request: Request, interval: str = "5m", instrument: str | None = None
) -> dict[str, Any]:
    require_instrument(instrument)
    try:
        bar_interval = BarInterval(interval)
    except ValueError as error:
        raise HTTPException(422, "UNSUPPORTED_TIMEFRAME") from error
    bars = fabric_of(request).bars("XAUUSD", bar_interval)
    return {
        "instrument_key": "XAUUSD",
        "interval": interval,
        "state": get_market_health(request)["state"],
        "source": request.app.state.xauusd_domain.provider,
        "authority_class": "BROKER_TICK_PROXY",
        "price_provenance": "BROKER_LAST_OR_QUOTE_DERIVED_BID",
        "bar_alignment_offset_minutes": 0,
        "bar_alignment_note": "UTC epoch alignment",
        "reason_codes": ["OBSERVED_TICKS_ONLY"],
        "candles": [
            {
                "bar_start": b.bar_start_utc.isoformat(),
                "bar_close": b.bar_close_utc.isoformat(),
                "open": str(b.open) if b.open is not None else None,
                "high": str(b.high) if b.high is not None else None,
                "low": str(b.low) if b.low is not None else None,
                "close": str(b.close) if b.close is not None else None,
                "volume": str(b.volume) if b.volume is not None else None,
                "tick_count": b.tick_count,
                "is_closed": b.is_closed,
                "open_interest": None,
            }
            for b in bars
        ],
    }


@router.get("/stream")
def get_market_stream(request: Request, instrument: str | None = None) -> StreamingResponse:
    require_instrument(instrument)

    async def events() -> AsyncIterator[str]:
        subscription = fabric_of(request).subscribe()
        try:
            while not await request.is_disconnected():
                health = get_market_health(request)
                yield (
                    "event: market\ndata: "
                    + json.dumps({"frame_kind": "FEED_STATE", "health": health})
                    + "\n\n"
                )
                try:
                    update = await subscription.get(timeout=1)
                    if update is None:
                        continue
                    yield (
                        "event: market\ndata: "
                        + json.dumps({"frame_kind": "TICK", "quote": get_market_quote(request)})
                        + "\n\n"
                    )
                except TimeoutError:
                    continue
        finally:
            subscription.close()

    return StreamingResponse(events(), media_type="text/event-stream")


@router.get("/footprint")
def get_footprint(request: Request) -> dict[str, Any]:
    return fabric_of(request).footprint()
