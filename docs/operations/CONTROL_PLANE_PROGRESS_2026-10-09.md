# ATS controllability implementation checkpoint

Baseline: audit commit 2f04a9715611da5fef65df033999ff06344e02c0. This checkpoint implements the first coherent integration phase. **It does not complete the full system-readiness mission.** External autonomous execution remains uncommissioned and no order was submitted.

## Delivered

- Registered accounts no longer silently fall back to standalone market data. Startup avoids a competing standalone feed when accounts exist; reconnect stops that feed.
- Broker account snapshots include every position/order, avoiding hidden non-XAUUSD exposure.
- Durable append-only account configuration revisions, optimistic revision checks, transactional account assignments/audit, and consent reset on save.
- Typed risk configuration: per-trade, daily/monthly, aggregate/strategy exposure, maximum lots/positions, margin allocation, paused entries and exact strategy-version assignments. 3%/8% are configuration ceilings, not an operational loss guarantee.
- Accounts UI for settings and assignments, with separate effective-readiness reasons. Saving cannot promote a research strategy or grant financial authority.
- Read-only broker lot sizing through the isolated authenticated session. Explicit costs, broker loss/margin calculations, volume-step flooring, minimum-lot rejection and margin-allocation checks. Preview remains provisional; unverified period accounting is explicitly excluded.
- Native observer status endpoint/panel: identity checks, bounded file size, file freshness, signal/clock/preset/permission state and no credentials. Native file state is not execution authority or independent UTC evidence.
- Account-bound validated live clock-evidence file and reload control; wrong-server/expired evidence rejects. Live evidence is not a historical timezone/DST profile.
- Origin guard rejects mutations from unrelated browser origins; reserved port3000 removed from default CORS. This is browser-origin hardening, not a complete authenticated operator-session system.
- Market displays actionable connection-required errors rather than stale fallback quotes.

## Physical read-only acceptance

Authenticated MT5 DEMO reconnect succeeded with execution consent false. At 2026-10-09 16:11:13 UTC, accepted XAUUSD tick freshness was approximately0.28 seconds, spread0.31, account-wide positions/orders both zero. Native file was recent and reported authority NONE, commands unsupported, signal CLOCK_PROFILE_REQUIRED and period ledger required.

Independent UTC tool plus a frozen native probe produced live-only clock evidence: offset10800 seconds, lifetime900 seconds, hash776354f180280286f97ab6329f3774453c3d5dcda6af7b303922351f0da769ac. It expires around16:25:50 UTC; after expiry the connector must degrade. Automatic independent renewal is **not implemented**.

A broker sizing request was rejected with MINIMUM_LOT_EXCEEDS_RISK: minimum0.01 lot required10.44 account-currency risk for the hypothetical10-price-unit stop plus44/lot modeled costs. The saved paused configuration uses0.5% per-trade risk,3% daily and8% monthly ceilings,1% aggregate/strategy risk, maximum0.10 lot/one position,30% margin allocation and no assigned strategies. These are operator settings, not a validated trading preset. Existing native research inputs are not modified by saving account risk settings.

## Validation

Full Python run before the last clock-reload addition:1640 passed, zero skipped, with local PostgreSQL enabled. Final contract/account tests after that addition:169 passed. Earlier run without PostgreSQL:1569 passed/69 skipped; those omissions were resolved by the PostgreSQL run. Separate integration/fault verification:137 passed.

Frontend62 tests passed: control-center45, API client10, UI7. Recursive typecheck and production build passed. Ruff/mypy passed. Formatting passed; lint has zero errors and three existing copilot any warnings. Browser verified the real settings/readiness controls and successfully saved paused configuration revision1. No financial action was used to test the UI.

## Remaining mission work

1. Automatic independently verified clock renewal and versioned historical clock mapping.
2. Typed executable strategy-parameter revisions, eligibility verifier and research-to-production evidence linkage. Current lineages remain RESEARCH.
3. Authenticated operator sessions/CSRF and complete command audit identity.
4. Trusted account-wide deal collector, net realized loss ledger, cash-flow treatment and verified UTC day/month equity baselines.
5. External account worker/router commissioning, authority-bound submit/partial-fill/timeout recovery, broker SL/TP readback and durable reconciliation.
6. Global/account/strategy kill switches, authorized reduction/manual exit/SL/TP changes and safe open-position ownership through restart/retirement.
7. Native proposal ingestion/parity/deployment receipts, Positions/Orders/Deals UI and linked evidence timelines.
8. Continuous bounded research scheduling and live trade-quality/Exit Watch integration.
9. MT4 authenticated transport and physical multi-account acceptance.

Do not label this checkpoint trading-ready. Software foundation checks and a current market-data connection do not substitute for external execution commissioning or strategy validation.

## Live execution request follow-up

External authority now requires explicit monthly cash loss/budget inputs, checks them at assessment and dispatch, and reserves pending risk against the monthly envelope. Missing monthly inputs fail validation; existing callers must supply them. The demo supervisor derives the monthly cash envelope from its verified period proof, preserving net realized P&L against start-of-month equity semantics. This does not commission broker period collection or impose a guaranteed realized-loss cap against gaps/slippage.

Accounts now prioritizes observed balances, quotes, freshness and reconciliation above configuration. Risk/readiness stays expanded; sizing and native diagnostics use accessible disclosure controls. Removed obsolete numbered-step copy.

Focused Python and contract verification: 202 passed. Frontend/type validation results recorded at completion. No account consent changed and no broker order submitted. External routing remains uncommissioned; trusted account-wide period accounting, reconciliation, eligibility and authenticated operator control remain prerequisites. This is a tested increment toward the requested live system, not trading-readiness acceptance.

Follow-up validation: 202 Python/contract tests passed, 45 control-center tests passed, TypeScript typecheck passed, execution-package mypy passed, and Ruff passed. One UI assertion initially referenced the removed numbered-step wording; updated to assert the current commissioning warning and reran the full control-center suite successfully. Production rebuild/live browser acceptance and remote CI for this increment have not run.
