# ATS Live Provider Architecture & Ingress Specification

## 1. Overview
The ATS Market Data subsystem ingests real-time market updates from the official Upstox V3 streaming WebSocket API, normalizes events into canonical representations, drives real-time multi-timeframe candle formation, logs append-only audit journals, and fans out updates to internal consumers (strategies, A04 risk veto, AI context builders) and external browser terminals.

## 2. Ingress Pipeline
1. **Authorizer (`UpstoxV3FeedAuthorizer`)**:
   - Exchanges bearer token for a single-use authorized WebSocket URI via HTTP GET to `https://api.upstox.com/v3/feed/market-data-feed/authorize`.
   - Never exposes or logs the ephemeral URI.
2. **Transport (`UpstoxV3LiveWorker`)**:
   - Maintains asynchronous WebSocket connection using `websockets.asyncio.client.connect`.
   - Sends binary UTF-8 subscribe frames (`subscribe_frame(mode=FeedMode.FULL, instrument_keys=(...))`).
   - Supervised by an 11-state deterministic state machine.
3. **Codec (`UpstoxV3ProtobufDecoder`)**:
   - Parses incoming binary frames against the pinned official Upstox V3 Protobuf schema (`FeedResponse`).
   - Normalizes feed variants (`ltpc`, `fullFeed.marketFF`, `fullFeed.indexFF`, `firstLevelWithGreeks`).
4. **Normalizer (`NormalizedFeedUpdate`)**:
   - Produces immutable, strongly-typed observations with nanosecond timestamps, LTP, bid/ask, cumulative volume, and open interest.
5. **Storage & Audit (`MarketJournal`)**:
   - Bounded in-memory deque (5,000 entries) with asynchronous background disk flusher.
   - Hourly rotating JSONL files (`journal_upstox_YYYYMMDD_HH.jsonl`).
6. **Candle Aggregator (`IncrementalCandleEngine`)**:
   - Real-time bucketed OHLCV aggregation for intervals: `1s DERIVED`, `5s DERIVED`, `15s DERIVED`, `1m`, `3m`, `5m`, `15m`, `30m`, `1h`, `1d`.
   - Enforces mathematical invariants: $H \ge \max(O, C), L \le \min(O, C), H \ge L$.
   - Handles cumulative volume without double counting.
7. **Distribution (`StreamHub`)**:
   - Multi-client WebSocket fanout server at `ws://127.0.0.1:8000/v1/stream/market`.
   - Channel-based subscriptions (`candle`, `quote`, `depth`, `oi`, `feed_health`).
   - Asynchronous non-blocking dispatch with 200ms per-client timeout preventing slow consumer backpressure.

## 3. Provider State Machine
```
DISCONNECTED
      │
      ▼
AUTHORIZING ──[Error]──► RECONNECTING ──► AUTHORIZING
      │
      ▼
 CONNECTING ──[Error]──► RECONNECTING
      │
      ▼
 CONNECTED
      │
      ▼
SNAPSHOT_PENDING
      │
      ▼
 STREAMING ──[Transport Loss]──► DEGRADED ──► RECONNECTING ──► AUTHORIZING
```
All transitions are recorded in `StateTransition` audit logs with timestamp, generation ID, attempt count, and reason.
