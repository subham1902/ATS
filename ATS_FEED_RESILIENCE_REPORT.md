# ATS Feed Resilience & Fault Recovery Report

## 1. Resilience Architecture
The live streaming subsystem is designed for zero-crash fault isolation and automated recovery:
1. **Single-Use Ephemeral URI Protection**:
   On disconnect or reconnect, the worker never reuses an old WSS URL; it unconditionally requests a fresh authorized URI via `UpstoxV3FeedAuthorizer`.
2. **Deterministic State Transitions**:
   Transitions follow an explicit legal graph (`STREAMING` -> `DEGRADED` -> `RECONNECTING` -> `AUTHORIZING` -> `CONNECTING` -> `SNAPSHOT_PENDING` -> `STREAMING`). No state is silently skipped.
3. **Bounded Backoff with Jitter**:
   Reconnection attempts follow exponential backoff: $t_{\text{wait}} = \min(2^k, 30.0) + \text{jitter}$, preventing thundering herd attacks against broker gateways.
4. **Volume Reset Protection**:
   `engine.reset_volume_tracking()` is triggered upon reconnect to prevent cumulative volume jumps from double-counting volume in forming bars.
5. **Fail-Closed Financial Safety**:
   If canonical broker data becomes stale ($> 30\text{s}$), the health state transitions to `STALE`, which causes A04 authority to block new trade entries (`UNKNOWN = NO NEW RISK`).
