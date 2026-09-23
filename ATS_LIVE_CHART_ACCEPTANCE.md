# ATS Live Moving Chart UI Acceptance Report

## 1. Acceptance Criteria Checklist
- [x] **Moving Candle Mutates in Real-Time**:
  Incoming ticks update the current active candlestick's high, low, close, and volume directly in the SVG DOM without page refresh.
- [x] **Interval Boundary Sealing**:
  When a bucket boundary passes, the previous candle is sealed into history (`final: true`) and a new candle starts.
- [x] **WebSocket Primary Transport**:
  Browser connects directly to `ws://127.0.0.1:8000/v1/stream/market`, receiving sub-second typed envelopes (`candle_update`, `candle_closed`, `quote`, `depth`, `oi`, `feed_health`).
- [x] **SSE Resilient Fallback**:
  If WebSocket is blocked or disconnected, client transparently falls back to `/v1/market/stream` SSE channel.
- [x] **Status Pill & Transport Badge**:
  Header visibly renders `● STREAMING (WEBSOCKET)` with green badge, switching to `STALE` or `OFFLINE` if connectivity drops.
- [x] **Technical Indicators Updating**:
  EMA20, EMA50, Bollinger Bands, and RSI calculate from the active live candle without future data leakage.
- [x] **SL / TP / Order Overlays Synchronized**:
  Dynamic SL and TP overlays from A04 / strategy prediction update alongside moving prices.
- [x] **Dual Source Switching**:
  `BROKER LIVE` and `OPEN TERMINAL` display sources switch cleanly without altering execution destination or financial authority.
- [x] **Playwright E2E Verification**:
  Windows-host Chromium acceptance suite passed with 0 console errors in both desktop (1440x900) and mobile (375x667) viewports.

## 2. Evidence Artifacts
- Desktop Market Streaming: `file:///C:/Users/subha/.gemini/antigravity-ide/brain/4fd21fa7-bce8-41a6-9245-97268504a312/screenshots/lc1_desktop_market_streaming.png`
- Mobile Market Streaming: `file:///C:/Users/subha/.gemini/antigravity-ide/brain/4fd21fa7-bce8-41a6-9245-97268504a312/screenshots/lc1_mobile_market_streaming.png`
