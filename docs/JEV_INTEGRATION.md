# ATS Jev Integration

This document outlines the integration of TypeSafe AI Jev via Vercel AI Gateway within the ATS platform.

## What Jev Does in ATS
Currently, Jev operates exclusively in **shadow mode**. It receives a safe, serialized snapshot of the ATS trading-engine candidate states (before authorization and risk execution). Jev evaluates this state and categorizes it across multiple analytical dimensions (`marketRegime`, `signalQuality`, `riskState`, `engineAgreement`, `anomalySuspected`, `requiresReview`). 

**Crucially, Jev has ZERO order authority.** It cannot place, modify, or cancel orders. Its evaluation runs asynchronously, ensuring that any AI provider outage, latency, or failure cannot interrupt or block ATS's normal operation.

## Architecture & Location
- **Python Backend**: The hook resides in `backend/src/ats/trading_runtime/orchestrator.py` during `_process_event`. It fires a background thread (to avoid blocking the main trading loop) that makes a synchronous HTTP request to the local Next.js API. Telemetry logic resides in `backend/src/ats/observability/jev_telemetry.py`.
- **Node/TypeScript Adapter**: Resides in `frontend/apps/control-center/app/api/jev/route.ts`. This acts as the translation layer between the raw ATS JSON snapshot and the Vercel AI SDK `experimental_evaluate` call. It ensures typed and safe evaluation schemas are enforced.

## Configuration Variables
The Jev integration respects the following environment variables (defined in `.env` / `.env.local`):

- `JEV_ENABLED`: (boolean) Set to `"true"` to enable evaluation. `"false"` completely bypasses the SDK.
- `JEV_MODE`: Typically `"shadow"`. Reserved for future logic if Jev transitions to an active advisory role.
- `JEV_MODEL`: E.g., `"typesafe-ai/jev"`. The provider model target.
- `AI_GATEWAY_API_KEY`: The authentication key for Vercel AI Gateway. **DO NOT COMMIT THIS KEY.**

## Shadow-Mode Behavior
When ATS reaches the candidate generation phase, it packages the candidate dictionary and timestamp, sending it via `urllib` in a `threading.Thread` to the Node adapter. The adapter structures this as a prompt, awaits the structured choice/boolean responses from Jev, and returns it. Python then logs this to `ats.jev_telemetry` but discards the result from the actual order/risk flow.

## How to Disable It
Simply set `JEV_ENABLED=false` in your local environment file, or remove the variable entirely. The Node adapter will immediately bypass evaluation and return `{ status: "disabled" }`. Alternatively, the background Python thread degrades gracefully if the API goes offline.

## How to Run the Smoke Test
Ensure the `.env` has the correct `AI_GATEWAY_API_KEY`.
1. Boot the Next.js control-center API:
   `pnpm --filter @ats/control-center dev`
2. Test the health endpoint:
   `curl http://localhost:3000/api/jev/health`
3. Test a synthetic evaluation:
   `curl -X POST http://localhost:3000/api/jev -d '{"direction": "BULLISH", "score": 0.95}' -H "Content-Type: application/json"`

## How to Run Jev Tests
- **Frontend (Node/TS):** 
  `cd frontend/apps/control-center && pnpm test`
- **Backend (Python):** 
  `cd backend && pytest tests/test_jev_shadow.py`

## Current Limitations
- Jev operates entirely post-facto on candidate states (shadow mode).
- The Python thread does not currently retry on transient Vercel API Gateway errors; it is strictly fire-and-forget to preserve execution safety.
- `urllib` is used to prevent the introduction of new HTTP dependencies (`httpx`/`requests`) into the frozen backend environment.
