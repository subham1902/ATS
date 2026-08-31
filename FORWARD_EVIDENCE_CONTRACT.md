# ATS Forward Evidence Contract

Version: 1.0  
Scope: counted NSE forward paper sessions after Session 02  
Authority: evidence only; no trading authority

## Governing rule

A forward session is valid only when its important facts can be reconstructed after complete process shutdown from the session directory alone. Terminal output, dashboard memory, process objects, and operator recollection are non-authoritative.

Every record is appended to `events.jsonl` with a contiguous sequence, payload hash, predecessor hash, event hash, UTC event/ingest/record times, session ID, producer, and typed payload. The recorder flushes and fsyncs every event. A write or fsync failure denies subsequent new-risk eligibility and invalidates research use.

## Required evidence

Every counted session requires lifecycle records (`SESSION_CREATED`, `SESSION_STARTED`, `SESSION_CLOSED`, `SESSION_SUMMARY_FINALIZED`), durable `STAGE1_RESULT`, Stage-2 connection/plan/sample/freshness records, signed raw `CLOCK_EVIDENCE`, normalized market events, feature results or explicit feature failures, production funnel attribution, shadow and same-state records, recorder health, and a passing hash chain.

Conditionally reached stages use their specific events: production prediction, thesis, candidate, Portfolio, Risk, A04, token, paper order, fill, position, exit and P&L. An unreached stage is written as `NOT_REACHED` with its upstream reason; absence is never converted into denial.

Option and shadow research use `OPTION_EVIDENCE`, `SHADOW_MODEL_STATE`, and `SAME_STATE_MODEL_RECORD`. Counterfactual money requires a linked `COUNTERFACTUAL_ENTRY` and `COUNTERFACTUAL_SETTLEMENT` containing contemporaneous contract, bid/ask, dynamic lot, entry/exit rules, cost version, timestamps, costs, and provenance. Otherwise monetary classification is `MONETARY_PNL_INVALID`; directional evidence may remain.

Scanner outcomes distinguish `NO_OPPORTUNITY`, `SCANNER_FAILED`, and `DATA_UNAVAILABLE` through typed reasons. Feature failures include `VOLUME_UNAVAILABLE`, `STALE_INPUT`, `INSUFFICIENT_HISTORY`, `CLOCK_INVALID`, and `MISSING_REFERENCE_DATA` as applicable.

## Clock and freshness contract

Raw provider age is signed and never clamped. Evidence records provider raw time, event/source/ingest/availability/decision times, raw provider age, normalized authority age, skew flag/magnitude, and normalization rule.

Canonical internal order is:

`event_time <= source_time <= ingest_time <= available_to_strategy_time <= decision_time`

Provider skew does not rewrite this truth. Unsafe or unknown normalization is stale/unknown and denies new risk. Receipt-clock authority is explicitly identified as `RECEIPT_CLOCK_AUTHORITY_V1`. The inclusive age boundary is: 1999 ms fresh, 2000 ms fresh, 2001 ms stale.

## Authoritative production separation

C0 remains `clamp(0.05, 0.95, 0.50 + 5.0 * ROC_3)` at threshold `0.55`. An authoritative C0 event exists only after a valid prerequisite feature state. The continuous dashboard calculation is labelled `NON_AUTHORITATIVE_OBSERVABILITY` and cannot enter production-funnel statistics.

Index volume is never fabricated. Current full-bar composition intentionally treats provider-present but volume-absent index bars as degraded (`VOLUME_UNAVAILABLE`) before production feature authority, even though the isolated C0 formula uses ROC_3. This conservative composition is retained; changing it requires a separately governed strategy/data-quality decision.

## Final artifacts

`manifest.json` contains the base ledger digest. `FORWARD_EVIDENCE_MANIFEST.json` contains source/config provenance, event counts/types, completeness flags, hash result, limitations, and deterministic validity. A report reconstructed after runtime destruction must agree with these artifacts.

