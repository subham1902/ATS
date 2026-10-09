# ATS small-account native workspace

`ATSSmallAccountObserver.mq5` is a compileable, read-only MT5 EA scaffold for
the new $500–$1,000 research variants. It records the authenticated terminal's
actual quotes, symbol precision/lot limits, account permissions and XAUUSD
positions. It does not replace the original `GoldTripleDemo`, alter its inputs,
or submit, modify or close orders. A running original EA remains a separate
autonomous system until it is deliberately retired and its positions reconciled.

The observer's `ATSAccountId` must match the durable ATS registry ID. Login and
password are never written to its files. Set the broker alias explicitly; base
and quote currency metadata must agree with XAU/USD where supplied. The default
requires a DEMO session. It freezes the initial account/server identity privately
and stops publishing account values if that identity changes.

Each timer update replaces `MQL5/Files/ATS/SmallAccount/<account-id>/account-state.json`
atomically. A changed observed tick appends an `ATS-MT5-OBSERVER-V1` JSON line to
`observations.jsonl`. No tick volume, aggressor, depth or price is synthesized.
Broker time is preserved raw, and `TimeGMT` has an explicit independence warning.
Net booked day/month P&L remains unknown until ATS supplies a verified UTC period
equity/deal ledger. The risk inputs describe requested ceilings, not executed
authority or a guarantee against a market gap.

## Execution integration path

1. Select the new intraday variant using chronological training and sealed
   validation, exact paired-data hashes and explicit broker costs/lot grid.
2. Port the parent publication, completed M1/M5 retest and exit rules with
   Python/MQL parity fixtures. The original EA assumes a particular broker DST
   clock; it must not be reused silently for another broker. Historical and live
   UTC mapping requires independent, date-aware evidence.
3. Feed the new proposal into ATS with versioned strategy ID, signal ID, dataset
   lineage, preset hash, side, entry zone, structural SL/TP and expiry. The EA
   does not issue authority or infer execution approval from Algo Trading.
4. ATS obtains account/deal/position facts through its isolated MetaTrader worker,
   reserves planned loss against day/month start equity and aggregate open risk,
   and issues account/mode/strategy/quantity-bound single-use authority. Unknown
   history, fees, identity or state blocks new risk; reductions remain a separate
   authorized route. `A2_PAPER` is ineligible for external execution.
5. Only the approved ATS execution adapter submits, with observed `OrderCalcProfit`
   sizing, minimum/step/max lot constraints, actual margin, fresh bid/ask,
   server-side SL/TP and durable idempotency. Unknown acknowledgments require
   reconciliation; no blind retry. Do not add a second native order engine.
6. Commission with one isolated DEMO account, explicit operator strategy/risk
   assignment, kill switches, filled-order/deal reconciliation and safe restart.
   A native EA attaching successfully is not proof ATS controls it.

An execution command file is intentionally not accepted: the current native EA
cannot validate or consume the ATS external ledger's authority. A file containing
an authority-looking string would not establish deterministic authorization.

## Build and lifecycle

The October 9 deployment uses a separate `ATSSmallAccountS3_1000` observer.
`scripts/install_small_account_observer.py --build-s3-profile` derives its input
defaults from the typed, hashed V3 S3 preset, verifies the registry identity and
an account-wide flat $1,000 USD DEMO session, preserves the existing chart profile,
and compiles with the official MetaEditor. This avoids initializing the generic
observer with its intentionally empty account ID. The installer does not attach
an EA or issue orders; attachment and emitted state must be independently verified.
The deployed observer was attached and its changing state/journal inspected.
Its signal state is `CLOCK_PROFILE_REQUIRED` and its execution authority is `NONE`.
The 3%/8% inputs describe requested caps, not completed broker execution enforcement.

MetaEditor on this installation returns process status 1 even when its diagnostic
log reports zero errors/warnings and produces the executable. The installer checks
the diagnostic log and binary and records that process status rather than claiming
an unexplained successful exit code.

Compile with the installed official MetaEditor, using an absolute source and log
path. Review a zero-error compiler log and record the source/executable hashes
before any controlled copy to `MQL5/Experts/ATSManaged/ATSSmallAccount`. Keep sources
and evidence in this versioned repository folder; generated `.ex5` and logs are
ignored. No deployment or attachment is performed by the compile step.

Before replacing/removing an active EA, inspect its chart, pending orders and
positions, preserve the previous source/executable/inputs, and retain managing
logic for existing exposure. Removing an EA must not leave an untracked position.
Installing this observer cannot safely take management ownership of original
`GoldTripleDemo` positions. New profitable research observations cannot be used
as inherited validation of the original three strategies or a live account.
