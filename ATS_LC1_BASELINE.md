# ATS-LC1 Runtime & Architecture Baseline

## 1. Runtime Baseline
- **Frontend URL**: `http://127.0.0.1:3001` (Next.js 16.3.2 Turbopack Control Center)
- **Backend URL**: `http://127.0.0.1:8000` (FastAPI / Uvicorn ASGI Server)
- **Port 3000 Protection**: Dedicated exclusively to `Digital Subham` (PID 34424). STRICTLY UNTOUCHED.
- **Operating System**: Windows 11 Host
- **Virtual Environment**: `d:\Projects\ATS\ats\.venv\Scripts\python.exe` (Python 3.11.15)
- **Execution Authority**:
  - `LIVE_MONEY`: `false` (Strict invariant)
  - `EXECUTION_DESTINATION`: `PaperBroker` only
  - `A04_AUTHORITY`: Final deterministic financial veto
  - `AI_AUTHORITY`: `NONE` (Zero order execution capabilities)

## 2. Upstox V3 Market Data Baseline
- **Provider Protocol**: Upstox Market Data Feed V3 (Protobuf Binary Wire Format)
- **Authorization Flow**: Ephemeral single-use WSS redirect URI acquired via `https://api.upstox.com/v3/feed/market-data-feed/authorize`
- **Credential Protection**: `ATS_UPSTOX_ANALYTICS_TOKEN` injected via runtime environment, wrapped inside `SecretStr`, zero leakage to logs, frontend bundles, or persistent storage.
- **Target Instrument**: `MCX_FO|569003` (MCX GOLDM FUT)
- **Feed Mode**: `FULL` (30-level L2 depth, cumulative VTT, real-time OI)

## 3. Streaming Engine Topology
```
[Upstox V3 WSS: wsfeeder-api.upstox.com]
                │  (Protobuf Binary Frames)
                ▼
  [UpstoxV3LiveWorker (Background Task)]
                │
        ┌───────┴────────────────────────┐
        ▼                                ▼
[Protobuf Decoder]              [Market Journal]
        │                       (Hourly JSONL)
        ▼
[MarketDataFabric]
        │
        ├────────────────────────┐
        ▼                        ▼
[IncrementalCandleEngine]   [StreamHub Fan-out]
(1s/5s/1m/5m/15m/1h/1d)          │
                                 ▼
                     [Client WebSockets]
                     (/v1/stream/market)
                                 │
                                 ▼
                     [Frontend LiveChart]
                     (Moving SVG Candle)
```
