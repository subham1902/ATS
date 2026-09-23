# ATS Internal Stream Hub Specification

## 1. Overview
`StreamHub` (`ats.market.live.stream_hub`) provides an in-process, non-blocking asynchronous message bus that fans out market events from a single upstream Upstox V3 provider connection to multiple downstream consumers (browser charts, strategy runners, A04 risk sentinels, AI live coach) without duplicating broker connections.

## 2. Protocol & Endpoints
- **Primary WebSocket**: `ws://127.0.0.1:8000/v1/stream/market`
- **Alias WebSocket**: `ws://127.0.0.1:8000/v1/market/ws`
- **Fallback Stream**: `http://127.0.0.1:8000/v1/market/stream` (SSE text/event-stream)

## 3. Client Control Messages
Clients send JSON control messages over the WebSocket:
- **Ping / Keepalive**:
  ```json
  {"action": "ping"}
  ```
  Response:
  ```json
  {"schema_version": "ats.market.v1", "type": "pong", "time": "2026-09-23T18:12:38Z"}
  ```
- **Subscribe**:
  ```json
  {
    "action": "subscribe",
    "instrument_key": "MCX_FO|569003",
    "interval": "5m",
    "channels": ["candle", "quote", "depth", "oi", "feed_health"]
  }
  ```
- **Unsubscribe**:
  ```json
  {"action": "unsubscribe", "instrument_key": "MCX_FO|569003"}
  ```

## 4. Backpressure Protection & Isolation
- Each connected client runs on an isolated async send channel.
- A strict 200ms timeout per client send prevents a slow or stalled browser tab from blocking other connected terminals or the backend upstream ingress loop.
- If a client exceeds the timeout, the dropped message counter is incremented, and dead or disconnected sockets are safely purged.
