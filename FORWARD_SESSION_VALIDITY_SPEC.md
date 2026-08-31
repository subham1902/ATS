# Forward Session Validity Specification

## Deterministic classifications

- `VALID_FORWARD_SESSION`: complete evidence, healthy recorder, Stage 2 and clocks proven, production attribution and same-state telemetry reconstructable, counterfactuals complete, option evidence present, and a previously uncounted NSE trading date.
- `VALID_FORWARD_SESSION_WITH_LIMITATIONS`: core validity passes but a declared non-authority research limitation remains, currently option evidence unavailable.
- `SUPPLEMENTAL_ONLY`: evidence is otherwise valid but the trading date is already represented by a counted valid session.
- `INVALID_STAGE2_EVIDENCE`: Stage-2 connection, plan, samples, or ready decision cannot be proven.
- `INVALID_CLOCK_EVIDENCE`: a required clock record is absent, incomplete, reordered, unsafe, or skew-normalization validity is unproven.
- `INVALID_PRODUCTION_FUNNEL`: lifecycle, feature/failure attribution, or same-state production/shadow facts are incomplete.
- `INVALID_OPTION_EVIDENCE`: claimed option economics lack contemporaneous durable quotes.
- `INVALID_COUNTERFACTUAL_EVIDENCE`: an entry lacks a complete forward-valid settlement; monetary attribution is invalid.
- `INVALID_RECORDER_HEALTH`: write/fsync/drop health is nonzero or missing.
- `INVALID_HASH_CHAIN`: sequence, payload hash, or predecessor chain fails.
- `INVALID_SAME_DAY_DUPLICATE`: reserved explicit duplicate-invalid classification; the runtime normally uses `SUPPLEMENTAL_ONLY` for same-day evidence.

## Evaluation precedence

Hash integrity, recorder health, Stage 2, clock truth, production reconstruction, distinct-day status, counterfactual completeness, and option limitations are evaluated in that order. A lower-priority success cannot mask an earlier failure.

Only `VALID_FORWARD_SESSION` and `VALID_FORWARD_SESSION_WITH_LIMITATIONS` may increment `FORWARD_SHADOW_CHAMPIONSHIP_VALID_SESSIONS`, and only once per persisted `trading_date`. `SUPPLEMENTAL_ONLY` never increments it.

## Stage-2 proof

The ready record must say `MARKET_OPEN_DATA_READY`, `all_required_fresh=true`, and `four_clock_valid=true`, with V3 LIVE state, expected/actual subscription counts, keys, samples, signed source/receipt ages, 2,000 ms threshold, and evaluation time available elsewhere in the same ledger. A global feed-health flag is insufficient.

## Zero-trade semantics

Zero trades is valid when Stage 2, market events, feature success/failure, why-no-trade attribution, same-state shadow outputs, recorder health, close/finalization, and integrity survive shutdown. Portfolio/Risk/A04 are `NOT_REACHED` when an upstream feature or thesis gate stops the cycle.

## Reconstruction procedure

1. Stop and finalize canonically.
2. Destroy runtime/process state.
3. Load only `events.jsonl` and `FORWARD_EVIDENCE_MANIFEST.json`.
4. Verify contiguous sequence, hashes, session identity, and completeness.
5. Reconstruct Stage 2, reasons, funnel, shadow records, options, trades and counterfactual settlements.
6. Apply this classifier.
7. Increment the forward-day count only for an allowed classification and a new trading date.

