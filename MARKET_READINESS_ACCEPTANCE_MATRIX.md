# ATS MARKET READINESS ACCEPTANCE MATRIX
**Target Version / Deployment**: A2 Paper Production-Like Operational Deployment  
**Worktree**: `D:\Projects\ATS\worktrees\final-a2-integration`  
**Branch**: `eng/final-a2-integration`  
**Target Trading Date**: Monday 2026-08-31  

| Subsystem | Classification | Evidence / Verification Method |
| :--- | :--- | :--- |
| **Repository** | `PASS` | Git working tree clean, HEAD `575d959`, `stash@{0}: D10-uncommitted-work-preserve` intact. |
| **Python Environment** | `PASS` | Python `3.11.15`, uv `0.12.1`, strict pyproject.toml dependencies verified. |
| **Node/pnpm Environment** | `PASS` | Pinned Node `v24.19.0`, pnpm `11.9.0` verified via toolchain check. |
| **Backend** | `PASS` | FastAPI server initializes cleanly on port 8000; `/health/live` and `/health/ready` return 200 OK. |
| **Frontend** | `PASS` | Next.js 16.3.2 Turbopack production build succeeds with 0 errors across all 18 routes. |
| **Upstox Authentication** | `PASS` | `UpstoxReadOnlyClient.ltp()` verifies live Bearer token without exposing credentials. |
| **Reference Authority** | `PASS` | `_fetch_reference(now)` downloads and parses official NSE BOD gzip contract master. |
| **InstrumentSpec** | `PASS` | Dynamically resolves NIFTY (lot 65, tick 0.050, exp 2026-09-01) & BANKNIFTY (lot 30, tick 0.050, exp 2026-09-29). Zero static production fallbacks. |
| **Feed Transport** | `PASS` | `UpstoxV3Transport` authorizes, connects, and test-subscribes via Protobuf WebSocket. |
| **Feed Decoder** | `PASS` | `UpstoxV3ProtobufDecoder` decodes binary wire frames into `NormalizedFeedUpdate`. |
| **Subscriptions** | `PASS` | `DynamicOptionUniverse` builds 20 ATM contracts with 0 duplicates, 0 invalid keys. |
| **Market Freshness** | `PASS` | Strict <= 2,000ms instrument-specific quote freshness enforced by Stage 2 data gate. |
| **Session FSM** | `PASS` | Calendar-driven FSM (`CLOSED`, `PREOPEN`, `ENTRY_ALLOWED`, `EXIT_ONLY`, `FLATTEN_WINDOW`). No hard-coded entry flags. |
| **Capital Authority** | `PASS` | Canonical `₹100,000` capital budget enforced; available/reserved/inflight tracked with 0 leaks. |
| **PaperBroker** | `PASS` | `PaperBrokerAdapter` simulates execution, fills, and slippage. No connection to real broker APIs. |
| **Portfolio Brain** | `PASS` | Enforces `ALLOW`, `ALLOW_REDUCED`, `DEFER`, `DENY` risk allocations. No LLM authority. |
| **Risk** | `PASS` | Capital stops, daily loss limits, drawdown de-escalation active. |
| **A04 Governance** | `PASS` | Final deterministic AND gate on all candidate entries and operational commands. |
| **C0 Model** | `PASS` | Production champion (`threshold = 0.55`, `P(UP) = clamp(0.05, 0.95, 0.50 + ROC_3 * 5.0)`). Strictly unchanged. |
| **Alpha V4 Model** | `PASS` | Wired as `SHADOW_ONLY`. `NetEV = None` when economics unavailable; zero order/token authority. |
| **M1–M9 Models** | `PASS` | Shadow models tracked in Forward Championship; zero production execution authority. |
| **R10-X Model** | `PASS` | Convexity/extreme-event shadow worker active without production authority. |
| **Harness** | `PASS` | `ADVISORY_ONLY` sidecar (4 agent sessions); governor-gated with zero order authority. |
| **Evidence Recorder** | `PASS` | Writes atomic `events.jsonl` with SHA-256 hash chains linked to session UUID. |
| **Hash Chain** | `PASS` | Verified mathematically via `SessionEvidenceRecorder.verify()`. |
| **Session Forensics** | `PASS` | `SessionEvidenceRecorder.finalize()` produces compliant `manifest.json` on session closure. |
| **Reconciliation** | `PASS` | Reconciles launcher state, dead PIDs, and closed ports (`CLEAN_NO_PRIOR_SESSION`). |
| **Launcher** | `PASS` | `scripts/start_ats_a2_live_paper.ps1` starts full stack idempotently. |
| **Shutdown** | `PASS` | `scripts/stop_ats_a2_live_paper.ps1` cleanly terminates processes and cleans up state file. |
| **Recovery** | `PASS` | Start-Stop-Start lifecycle test passes; fails closed on missing/stale data. |
| **Operator API** | `PASS` | Exposes `/v1/runtime/status`, `/v1/pipeline/counters`, `/v1/forensics/*` schemas. |
| **Control Center** | `PASS` | Control Center UI renders backend truth accurately with zero positions / off-market states. |
| **Performance** | `PASS` | Low-latency asynchronous pipeline; shadow evaluation does not block C0 decision path. |
| **Failure Isolation** | `PASS` | Provider disconnect, stale ticks, missing metadata, and shadow exceptions all fail closed. |
