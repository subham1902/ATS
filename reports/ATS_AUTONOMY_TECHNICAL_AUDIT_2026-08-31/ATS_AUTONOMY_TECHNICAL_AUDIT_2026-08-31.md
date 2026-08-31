# ATS autonomy and profitability-readiness technical audit

**Audit date:** 2026-08-31 IST  
**Audited branch:** `eng/final-a2-integration`  
**Starting checkpoint:** `de4ca8a2c3ba0eedc880670a847ab26356a24c9b`  
**Execution scope:** A2 paper only; live money disabled; no real broker-order calls  
**Current operational verdict:** **NOT READY FOR UNATTENDED MARKET EXECUTION**  
**Forward-alpha verdict:** **SESSION_NOT_VALID_FOR_FORWARD_ALPHA**

## Technical summary

The system has a substantial safety architecture, but the frozen checkpoint was not ready for a genuine unattended forward session. Three production defects directly threatened Session 01 validity: the execution controller did not enforce the external market-open gate, the live runtime accepted quotes up to 10 seconds old despite the 2-second charter, and real option evidence accessed fields that do not exist and then swallowed the resulting exception. These defects were repaired outside an active session without changing C0, its 0.55 threshold, Portfolio Brain, Risk, A04, costs, sizing policy, or challenger authority.

The audit also found that the published qualification status overstated the evidence. The full Python suite's apparent success was caused by a session-wide autouse PostgreSQL fixture that skipped 1,741 tests when no database DSN was present. Correcting that fixture exposed stale execution fixtures, which now declare explicit replay lot authority. Full backend mypy now passes across 305 source files. All 80 frontend tests and the production build pass. The broad Python suite reached 99% without failures after the repairs, but two computational research tournament tests were bounded rather than allowed to run indefinitely; PostgreSQL integration tests still require an external database.

No evidence supports a promise of good profits. C0 is a simple three-bar rate-of-change rule, historical calibration is based on underlying returns rather than realized option payoffs, and the challenger tournament does not inject challenger predictions into the controller used to produce trading metrics. The correct next step is a freshly qualified, observable paper session—not model promotion or capital deployment.

## Decision snapshot

| Area | Status | Evidence-backed conclusion |
|---|---|---|
| Live-money safety | PASS | Paper target remains enforced; no real-order endpoint was called; recorded real broker orders remain zero. |
| Stage 2 execution authority | FIXED, REQUALIFICATION REQUIRED | New risk now fails closed until the attached V3 feed is LIVE and all 22 dynamic subscriptions are fresh. |
| Decision freshness | FIXED, REQUALIFICATION REQUIRED | Production feed silence and stale thresholds now use inclusive 2,000 ms semantics. |
| Live option telemetry | FIXED | Runtime now reads `last_price`, direct IV, delta, and theta fields; scanner failures are counted. |
| Forensics discovery | FIXED | Canonical `manifest.json` is now discovered, new manifests preserve session identity, and legacy manifests remain readable. |
| Backend typing | PASS | Mypy: 305 source files, zero errors. |
| Changed-code lint | PASS | All modified production and focused test files pass Ruff. |
| Repository-wide lint | FAIL | 303 findings remain, primarily formatting/import debt and test-code hygiene. |
| Frontend | PASS WITH ENVIRONMENT WARNING | 80 tests pass and 18 static routes build; the shell currently exposes Node 26.4.0 while the package requests Node 24.19.0. |
| Dependency audit | PASS | `pnpm audit --prod`: no known vulnerabilities. |
| Genuine forward evidence | NOT AVAILABLE | The only finalized session was off-hours, contained four lifecycle events, zero observations, zero predictions, and zero trades. |
| Profitability evidence | NOT ESTABLISHED | No valid forward option-economic sample exists. |

## Scope, evidence, and definitions

The audit covered runtime lifecycle, execution safety, Upstox V3 ingestion, option evidence, freshness, autonomous scanning, Portfolio Brain and A04 routing, paper fills, evidence finalization, forensic reads, test collection, static analysis, frontend contracts, build output, dependency audit, calibration provenance, and research tournaments. It did not place orders, call a broker order endpoint, modify model thresholds, promote a challenger, or run a genuine market-open session.

“Autonomous-ready” means that the system can launch through the canonical path, obtain authoritative current instruments, block new risk until every decision-critical subscription is fresh, generate predictions without operator-created candidates, route legitimate C0 candidates through unchanged deterministic authorities, fail closed on stale or invalid evidence, flatten and finalize canonically, and produce verifiable evidence. “Profitable” requires forward net returns after all real costs with adequate sample size and robustness; no replay pass or zero-trade smoke session satisfies that definition.

## Production correctness findings and changes

### Market-open acceptance was advisory instead of authoritative

The standalone acceptance script could return `MARKET_OPEN_DATA_READY`, but the controller's execution path did not consume that verdict. A candidate could reach allocation and authority based only on session and partial freshness checks. The controller now performs an internal invariant check immediately before allocation: production live-evidence mode requires a LIVE connection, exactly 22 dynamic subscriptions, and `FRESH` state for every subscription. Failure returns `MARKET_OPEN_DATA_NOT_READY`, increments a typed rejection, forces the runtime read model's `can_enter` false, and submits no paper order.

### Freshness policy contradicted the market-day charter

The engine and selector used 2,000 ms, while the session config and live supervisor used 10,000 ms. The session and V3 supervisor now use 2,000 ms for both maximum silence and staleness, preserving the existing inclusive semantics. This is intentionally stricter and may reduce trade frequency; reduced activity is preferable to acting on stale option economics.

### Real option evidence could disable scanning invisibly

`OptionQuote` exposes `last_price`, `implied_volatility`, `delta`, and `theta` directly. The runtime accessed nonexistent `mark_price` and nested `greeks` attributes. At market open, this would raise an attribute error; the scanner's broad exception boundary would suppress it and return no result. The field access is corrected and a `scanner_failures` counter is exported so future isolated failures are visible.

### Session forensics could not discover canonical finalized sessions

The recorder writes `manifest.json`; discovery searched for `session_manifest.json`. The reader also called a nonexistent `_load_events` method and referenced missing imports. Discovery now uses the canonical manifest, new manifests embed the full session identity, and legacy manifests reconstruct location-critical identity from the first verified event. The previously finalized off-hours session now reads as integrity `VALID`, with four events and the expected zero-activity summary.

### Test collection concealed most of the repository

An autouse session-scoped PostgreSQL migration fixture caused unrelated tests to skip whenever `ATS_TEST_POSTGRES_DSN` was absent. Removing autouse scope confines the skip to tests that actually request the database fixture. Stale replay execution tests now register explicit fixture lot sizes rather than weakening production's provider-authority requirement.

## Profitability and model findings

### C0 has no demonstrated forward economic edge

The frozen champion computes probability from three-bar rate of change around 0.50 and activates at 0.55. In practical terms, the linear segment needs approximately a one-percent three-bar underlying move to cross the bullish threshold, with a symmetric bearish test. This can legitimately yield compressed probabilities and zero trades in quiet index conditions. The audit did not change the formula or threshold because one session—or no session—is not sufficient tuning evidence.

### Historical calibration is not genuine option-payoff evidence

The default calibration store is an absolute external path, outside the worktree, and is not bound to the Git checkpoint by a checked-in manifest and content hash. The historical builder assigns deterministic ingestion/availability clocks because REST candles do not contain the original live clocks. More importantly, calibration outcomes are based on underlying returns. They can support directional calibration research but cannot establish realized option payoff after bid/ask spread, depth, slippage, brokerage, statutory charges, IV movement, theta, and liquidity.

### Instrument selection uses an economic proxy

Expected gross option P&L is estimated from underlying expected return multiplied by option delta and lot size, followed by modeled penalties and costs. That is a useful screening proxy, not observed future option payoff. Under the charter's no-synthetic-option-economics rule, promotion-quality claims must come from contemporaneous provider option quotes and later realized option outcomes. If that evidence is unavailable, the correct Alpha V4 action remains HOLD with `ECONOMIC_PAYOFF_EVIDENCE_UNAVAILABLE`.

### Challenger execution comparisons are not attributable

The challenger tournament uses each model's probability function for forecast metrics, but its order/fill/P&L loop creates the ordinary A2 controller without injecting that challenger function. The resulting trading metrics therefore describe the production controller, not each challenger. A separate champion-replacement tournament synthesizes ATM option price assumptions and contains legacy lot-size constants. Neither output is promotion-grade. C0 must remain champion, and M2, R10-X, and Alpha V4 must remain shadow/research only.

### Placeholder market evidence contaminates research telemetry

The scanner constructs some snapshot fields with fixed volume and zero freshness, while prediction telemetry includes fixed cost/net-EV placeholders. These values must not be interpreted as real market economics. They were not changed in this hardening pass because replacing them requires a broader evidence-schema decision; they are a priority before any profitability claim.

## Operational and security findings

The API exposes a localhost manual paper-order seam in addition to the autonomous path. It is lot-, freshness-, capital-, session-, and A04-governed and cannot place real broker orders, but it can contaminate an autonomous experiment if used. Runtime command and manual paper-order endpoints rely on localhost placement rather than application authentication. For Forward Session 01, the operator should not use the manual ticket; a future hardening release should disable manual entry by default in forward-experiment mode and authenticate local mutations.

The session calendar includes the current date without authoritative weekend/holiday validation. Exchange timing documentation now lists equity derivatives through 15:40 after the Closing Auction Session changes effective August 2026, while ATS intentionally stops risk and closes earlier. Keeping the conservative internal 15:30 close is safe, but documentation should call it the ATS policy close rather than the exchange close. Holiday/BOD authority must remain a fresh Stage 1 dependency.

The frontend package requests Node 24.19.0, while the current audit shell reports Node 26.4.0. Tests and build pass, but market-day execution should use the pinned toolchain to avoid an unsupported-engine drift.

## Validation results

| Check | Result |
|---|---|
| Canonical reconciliation before changes | `CLEAN_NO_PRIOR_SESSION` |
| Focused runtime/forensics Python tests | 41 passed |
| Additional reader regression tests | 2 passed |
| Backend mypy | 305 source files; zero errors |
| Modified-file Ruff | PASS |
| Repository-wide Ruff | 303 findings remain |
| Broad Python suite | Reached 99% with no failure after fixes; bounded during a long research tail |
| PostgreSQL tests | Skipped only when their required external DSN is absent |
| Frontend tests | 80 passed |
| Next.js production build | PASS; 18 static pages generated |
| Production dependency audit | No known vulnerabilities |
| Finalized off-hours session integrity | VALID; four lifecycle events; zero market observations |

The broad suite is not reported as a complete pass because the long research tests were stopped after a bounded wait. The repository-wide Ruff result also prevents repeating the earlier blanket “Ruff PASS” claim. These limitations are deliberate and visible.

## Market-day acceptance checklist

Before unattended paper operation, create a reviewed documentation/correctness commit, then rerun the canonical qualification on the exact resulting HEAD. At approximately 09:00 IST, require a clean worktree, the expected branch and reviewed HEAD, intact preservation stash, fresh Stage 1 provider/BOD/V3/subscription/instrument truth, paper-only configuration, ₹100,000 capital, clean reconciliation, and the pinned runtime toolchain. Do not launch on a `BLOCKED_` verdict.

Launch only through the canonical AGGRESSIVE paper script. At and after 09:15, independently verify increasing raw, normalized, and fresh counts; a LIVE V3 connection; 22 current dynamic subscriptions; all NIFTY/BANKNIFTY underlying and option keys at or below 2,000 ms; valid four-clock ordering; and the internal execution gate reporting ready. A global health flag alone is insufficient.

During the session, monitor `scanner_failures`, staleness, resynchronization, C0 prediction dispersion, exact funnel reachability, shadow-only decisions, option-economic availability, evidence sequence growth, paper positions, and real-order count. Do not restart for zero trades, lower the threshold, create candidates manually, or promote a challenger. At cutoff and flatten, use only canonical lifecycle commands and verify the finalized manifest/hash chain.

## Limitations and robustness

This audit occurred before the target market open and did not validate live Upstox authentication, current Monday contracts, subscription entitlement, exchange BOD, live latency distribution, disconnect recovery, real option depth/Greeks, autonomous candidate generation, paper fills, exit behavior, or end-of-day finalization under genuine NSE flow. It therefore cannot certify Forward Session 01 or estimate expected profit.

Open-source and official documentation were used to validate provider semantics, time-series evaluation principles, probability calibration, exchange timing, and regulatory context. External research supports purged chronological evaluation, calibration assessment, and multiple-testing controls; it does not validate ATS-specific edge.

## Prioritized next actions

1. Review and commit only the demonstrated correctness/safety changes; bind the new HEAD to an updated acceptance record.
2. Run the full pinned-toolchain qualification, including a real PostgreSQL test service and the bounded research tests separately from market-critical CI.
3. Execute fresh Stage 1 and Stage 2 on the target date. If either fails, do not launch risk.
4. Collect Forward Session 01 with no manual entries and verify the new Stage 2 and scanner-failure evidence.
5. Build a versioned, hashed calibration manifest and collect genuine option outcome labels before assessing profitability.
6. Repair challenger tournament attribution and eliminate synthetic option-price assumptions before any promotion study.
7. Disable or authenticate local mutation routes for forward-experiment mode.
8. After five valid forward sessions, evaluate calibration, net economic results, drawdown, data quality, and model comparisons. Do not promote from Session 01.

## Final status

The system is materially safer and more observable than the starting checkpoint, but it is not yet certified for unattended market execution and has no demonstrated profit guarantee. The only defensible forward-session verdict at audit time is:

**SESSION_NOT_VALID_FOR_FORWARD_ALPHA**

Recommended operational action: **REQUALIFY_CORRECTED_HEAD_THEN_COLLECT_FORWARD_SESSION_01**.

## Sources

- Repository source and tests at the audited branch and working changes.
- [Upstox Market Data Feed V3](https://upstox.com/developer/api-documentation/v3/get-market-data-feed/)
- [Upstox V3 authorization](https://upstox.com/developer/api-documentation/get-market-data-feed-authorize-v3/)
- [Upstox option Greeks](https://upstox.com/developer/api-documentation/option-greek/)
- [NSE market timings](https://www.nseindia.com/static/market-data/market-timings)
- [NSE Closing Auction Session](https://www.nseindia.com/static/products-services/closing-auction-session)
- [SEBI safer participation of retail investors in algorithmic trading](https://www.sebi.gov.in/legal/circulars/feb-2025/safer-participation-of-retail-investors-in-algorithmic-trading_91614.html)
- [scikit-learn TimeSeriesSplit](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html)
- [scikit-learn probability calibration](https://scikit-learn.org/stable/modules/calibration.html)
- [White, A Reality Check for Data Snooping](https://onlinelibrary.wiley.com/doi/pdf/10.1111%2F1468-0262.00152)
- [Bailey et al., The Probability of Backtest Overfitting](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2308659)
- [Bailey and López de Prado, The Deflated Sharpe Ratio](https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf)
