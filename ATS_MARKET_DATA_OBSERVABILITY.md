# ATS Market Data Observability & Telemetry

## 1. Metrics Surface
Real-time telemetry is exposed through `GET /v1/market/health` and broadcast via `feed_health` WebSocket frames:

| Metric | Source | Current Verified Value | Description |
| :--- | :--- | :--- | :--- |
| `state` | Fabric | `LIVE` | Overall distribution health state |
| `provider_state` | State Machine | `STREAMING` | Upstream broker connection lifecycle state |
| `reconnect_count` | Worker | `0` | Total upstream transport reconnections |
| `events_received` | Worker | `> 1` | Total market observation events decoded |
| `decode_errors` | Protobuf Codec | `0` | Number of unparsable or malformed frames |
| `quote_age_ms` | System Clock | `~300 ms` | Milliseconds since latest quote tick |
| `trade_age_ms` | System Clock | `~300 ms` | Milliseconds since latest trade tick |
| `depth_age_ms` | System Clock | `~300 ms` | Milliseconds since latest L2 order book update |
| `oi_age_ms` | System Clock | `~300 ms` | Milliseconds since latest open interest update |
| `active_stream_clients` | StreamHub | `1` | Connected WebSocket client terminals |
| `journal_memory_depth` | Journal | `> 0` | In-memory buffered audit events |
| `journal_overflow_count` | Journal | `0` | Dropped audit events under extreme pressure |

## 2. Telemetry Invariants
- Zero synthetic green: If no updates have been received, the endpoint reports `NO_FEED` or `STALE`, never fabricating timestamps.
- Zero secret leakage: Auth tokens, client IDs, and ephemeral WebSocket URIs are strictly excluded from all telemetry responses.
