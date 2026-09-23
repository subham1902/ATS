# ATS History + Live Seam Reconciliation Specification

## 1. Overview
When a client chart loads or reconnects, it must seamlessly bridge historical data with the live streaming mutable bar without creating duplicate boundary candles or gaps.

## 2. Stitching Algorithm
1. **Historical Baseline Load**:
   - Client requests historical bars via `GET /v1/market/candles?interval={itv}&instrument={key}&limit={N}`.
   - Backend retrieves historical bars from normalized reference storage (`load_historical_reference_candles`).
2. **Live Feed Attachment**:
   - Backend appends live bars currently tracked by `MarketDataFabric` and `IncrementalCandleEngine`.
   - Any historical bar whose timestamp overlaps with the first live bar's timestamp is discarded in favor of authoritative live exchange updates:
     $$\text{Stitched} = \{ C_{\text{hist}} \mid t < t_{\text{first\_live}} \} \cup \{ C_{\text{live}} \}$$
3. **In-Flight Stream Merging**:
   - Once WebSocket connection opens (`/v1/stream/market`), incoming `candle_update` envelopes mutate the final bar in the array in-place.
   - When a `candle_closed` event arrives, the client marks the bar as sealed and appends the new bar on the subsequent `candle_update`.
4. **Timeframe Switch Reconciliation**:
   - Upon interval change (e.g. `5m` -> `15m`), the client fetches the new timeframe's historical baseline and subscribes to the matching interval channel on the WebSocket, avoiding interval mismatch.
