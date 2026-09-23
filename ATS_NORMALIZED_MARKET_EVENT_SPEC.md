# ATS Normalized Market Event Specification

## 1. Scope
Defines the canonical, provider-neutral market data event schema used across the ATS trading runtime, market fabric, candle engine, and client fan-out streams.

## 2. Event Types
The streaming pipeline recognizes and emits the following typed envelopes:

### 2.1 `candle_update`
Emitted whenever an incoming trade or quote observation updates the currently forming working candle.
```json
{
  "schema_version": "ats.market.v1",
  "type": "candle_update",
  "source": "BROKER",
  "provider": "upstox",
  "instrument_key": "MCX_FO|569003",
  "interval": "5m",
  "is_derived": false,
  "time": "2026-09-23T18:10:00Z",
  "source_time": "2026-09-23T18:12:10Z",
  "ingest_time": "2026-09-23T18:12:10.460Z",
  "bar": {
    "time": "2026-09-23T18:10:00Z",
    "bucket_start_epoch": 1727115000,
    "open": 151390.0,
    "high": 151405.0,
    "low": 151365.0,
    "close": 151394.0,
    "volume": 25,
    "open_interest": 37440,
    "final": false,
    "volume_status": "EXACT",
    "tick_count": 42
  }
}
```

### 2.2 `candle_closed`
Emitted at the exact interval boundary when a candle finishes and is sealed into history.
```json
{
  "schema_version": "ats.market.v1",
  "type": "candle_closed",
  "source": "BROKER",
  "provider": "upstox",
  "instrument_key": "MCX_FO|569003",
  "interval": "5m",
  "is_derived": false,
  "time": "2026-09-23T18:10:00Z",
  "bar": {
    "time": "2026-09-23T18:10:00Z",
    "open": 151390.0,
    "high": 151405.0,
    "low": 151365.0,
    "close": 151394.0,
    "volume": 320,
    "open_interest": 37440,
    "final": true
  }
}
```

### 2.3 `quote`
Emitted on price, bid/ask, or quantity updates.
```json
{
  "schema_version": "ats.market.v1",
  "type": "quote",
  "source": "BROKER",
  "provider": "upstox",
  "instrument_key": "MCX_FO|569003",
  "quote": {
    "ltp": 151394.0,
    "bid": 151363.0,
    "ask": 151395.0,
    "volume": 32597,
    "open_interest": 37440,
    "exchange_timestamp": "2026-09-23T18:12:10.460Z"
  }
}
```

### 2.4 `depth`
Emitted when L2 order book levels change (FULL mode).
```json
{
  "schema_version": "ats.market.v1",
  "type": "depth",
  "source": "BROKER",
  "provider": "upstox",
  "instrument_key": "MCX_FO|569003",
  "depth": {
    "bids": [{"price": 151363.0, "quantity": 10}],
    "asks": [{"price": 151395.0, "quantity": 10}]
  }
}
```

### 2.5 `feed_health`
Emitted periodically or on transport state changes.
```json
{
  "schema_version": "ats.market.v1",
  "type": "feed_health",
  "source": "ATS",
  "health": {
    "provider_state": "STREAMING",
    "reconnect_count": 0,
    "events_received": 1420,
    "decode_errors": 0,
    "quote_age_ms": 309,
    "trade_age_ms": 309,
    "depth_age_ms": 309,
    "oi_age_ms": 309,
    "active_stream_clients": 1
  }
}
```
