# Execution control readiness — 2026-10-09

Status: NOT COMMISSIONED. Autonomous broker execution remains disabled.

## Implemented and tested

- Immutable, hash-checked account-wide deal snapshots and observed UTC day/month equity baselines.
- Net realized P&L includes profit, commission, fees and swap. Deposits/withdrawals reconcile balance but do not count as trading profit or change the period equity denominator.
- Explicit configured caps of at most 3% daily / 8% monthly; negative remaining budgets remain negative.
- Unknown history, historical clock provenance, baseline, currency/account identity, stale data or balance mismatch produces UNKNOWN; no zero-loss fallback.
- Monthly pending-risk reservations counted before reserve and again immediately before dispatch. Demo period facts must agree with observed monthly losses.
- Account-wide pure reconciliation compares ATS-owned exposure with broker volume, side, symbol, SL/TP, identity and freshness. Manual/other-symbol exposure is visible as unowned risk. A missing position is not proof of closure. Unknown acknowledgements cannot be cleared by a flat snapshot.
- Read-only budget API/UI; public clients cannot write evidence. Expired budgets are hidden rather than displayed as current capacity.

## Verification

- Full Python suite with local PostgreSQL: 1,680 passed, 0 failed, 0 skipped. XML: reports/execution-controls-pytest.xml.
- Frontend workspace: 66 passed (49 control-center, 10 API-client, 7 UI).
- Ruff and whole-backend mypy passed. Recursive TypeScript checks and production build passed.
- Lint: 0 errors; 3 pre-existing copilot any warnings.
- Runtime rebuilt and started with ats-start on 3001/8100; port 3000 preserved.
- Browser verified account monitoring, disabled execution consent and UNKNOWN budgets. Actual local budget endpoint reports PERIOD_HISTORY_OR_BASELINE_REQUIRED.
- No broker order, account execution enablement or strategy promotion occurred.

## Operator handoff

Open Accounts and review market freshness, broker snapshot, account risk settings and readiness. Loss budgets need genuine UTC boundary snapshots and fully reconciled history; syntax-valid input is not independent proof. The ledger cannot reconstruct missing historical equity from today's account balance. Internal comparator/ledger results are not authorization to trade.

This report is a readiness assessment, not an instruction to enable real-money execution. No activation action was performed.

## Required before commissioning

1. Trusted broker deal collection with versioned historical timezone/DST evidence and actual day/month boundary observations.
2. Durable execution/deal lifecycle reconciliation and validated reservation release; restart/unknown-ack recovery.
3. Independently verified strategy/version/dataset/cost evidence and native/Python rule parity.
4. Authenticated operator sessions, CSRF protection and actor-bound audit; complete kill-switch/reduction control lifecycle.
5. Isolated execution-worker/router commissioning, protective-order readback and end-to-end fault acceptance using mocks/paper first.
6. Independent clock renewal and physical account/terminal acceptance. MT4 authenticated execution remains unconfigured.

Software risk ceilings cannot guarantee losses stay below caps during gaps, slippage or broker failure. No strategy profitability or calibrated success probability is established by this work.
