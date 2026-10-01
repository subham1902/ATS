# MCX Gold Strategy Readiness Audit

**Date:** 2026-10-01
**Author:** Claude Sonnet 5 (audit), reviewed against primary artifacts only
**Scope:** All MCX-Gold-adjacent strategy work in the ATS workspace, evaluated against
the ATS Strategy Research Standard's 7-phase gate model and 7-state promotion ladder.
**Explicitly out of scope:** implementation of new code. This is a status/evidence audit only.

---

## 0. Headline Finding

**Zero strategies are promoted past CANDIDATE / RESEARCH_ONLY anywhere in the workspace.**
Every strategy family that has been evaluated — native (S01-S35, B00-B04), imported
(`BIN_S01`-`BIN_S09`), and the one hash-frozen strategy (S17) — currently sits at
`REJECTED`, `DATA_BLOCKED`, or `INSUFFICIENT_EVIDENCE`. No strategy has produced the 20
resolved forward outcomes required even to be considered for `PAPER_ELIGIBLE`. This is the
correct, honest state for a system whose real MCX GOLDM data (Volume + OI) does not yet
exist — it should not be read as a failure of the research process.

---

## 1. Naming-Scheme Collisions (data-hygiene finding)

Four independent, non-reconciled strategy ID namespaces exist in the workspace simultaneously:

| Namespace                | Where                                      | Example IDs                                                                                                                                                                 |
| ------------------------ | ------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Canonical taxonomy       | ATS Strategy Research Standard v1.0        | S1-S14 (by _mechanism family_, e.g. "Opening Range Breakout")                                                                                                               |
| STRAT-04 survivor report | `ATS_STRAT_04_SURVIVOR_REPORT.md`          | S01-S35, B00-B04 (by _registration order_, unrelated to canonical S1-S14 meaning)                                                                                           |
| `agents/strategies.py`   | `ats/backend/src/ats/agents/strategies.py` | Internal `sid` values that **collide with each other**: `S02_TSMOM` (line 340) vs. `S02_MICRO_TICK` (line 538); `S03_DONCHIAN_ATR` (line 107) vs. `S03_GAP_FILL` (line 587) |
| BIN import series        | `ATS_BIN_01/02_FINAL_REPORT.md`            | `BIN_S01`-`BIN_S09`, mapped to real model names (`crabel_orb_nr7_model`, `fabio_amt_playbook`, etc.)                                                                        |

**Corrected finding (verified in code, 2026-10-01).** The full IDs are _distinct_
(`S02_TSMOM` vs `S02_MICRO_TICK`, `S03_DONCHIAN_ATR` vs `S03_GAP_FILL`); there is no
duplicate full ID. The defect was **prefix aliasing**: `strategy_registry_service.py` and
`lab_service.py` reduced an ID to the text before the first `_` and looked that up, so
both `S02_*` strategies resolved to the same `S02` key. That key is also the registry's
own STRAT-04 registration-order `S02` (a different strategy), so live/paper performance
and leaderboard scores could be attributed to the wrong strategy. Fixed in commit
`94a55c0`: lookups are exact full-ID matches via `ats.strategies.identity`, a bare prefix
is rejected as ambiguous, and any legacy alias must be listed explicitly (none are).
**Not done:** no ID was renamed; whether to rename for clarity is a separate migration
decision (about a dozen files reference these IDs). Registry-key `S02`/`S03` (STRAT-04)
and agent-lab `S02_*`/`S03_*` remain two different namespaces and must not be joined on
the prefix.

---

## 2. STRAT-02 Provenance Discrepancy (data-hygiene finding)

STRAT-04's survivor report (`ATS_STRAT_04_SURVIVOR_REPORT.md`) states:

> "This outcome independently corroborates the platform's prior STRAT-02 finding (where 20
> strategies were rejected under MCX PIT V3 costs)..."

This claim has been repeated in multiple earlier project summaries as established history.
**It does not match the only STRAT-02-labeled artifact that actually exists in the
workspace.** `worktrees/goldm-day0/ATS_STRAT_02_FROZEN_BASELINE.json` (frozen
2026-09-17T23:25:00Z) is **not** a 20-strategy rejection tournament. Its full content:

```json
{
  "description": "ATS-STRAT-02 Frozen Baseline Evidence Hashes",
  "frozen_at": "2026-09-17T23:25:00Z",
  "cost_model_version": "goldm-pit-cost-v3",
  "strategies_validated": ["S17"],
  "artifacts": { ... three evidence-hash entries for S17 only ... }
}
```

This is a **hash-freeze of a single strategy's (S17) evidence artifacts**, for
reproducibility, not a rejection tournament of 20 strategies. No STRAT-02 rejection-tournament
artifact (log, CSV, or report naming the 20 rejected strategies) was found anywhere in the
workspace after an exhaustive grep.

**Conclusion:** the "20 strategies rejected under STRAT-02" claim is STRAT-04's own
secondhand narrative about its own history, not independently verifiable against a STRAT-02
source document. It may be true (STRAT-04's own 40-family evaluation did reject all but the
same shared cost model), but it should not be cited as corroboration from a separate,
independent study — on current evidence it is unconfirmed, and the one real STRAT-02
artifact is unrelated to it.

**Recommendation:** Either locate the real STRAT-02 rejection-tournament artifact, or amend
STRAT-04's report to drop the corroboration claim.

---

## 3. STRAT-04 Survivor Report — Status

Source: `ATS_STRAT_04_SURVIVOR_REPORT.md` and `ATS_SURVIVOR_PORTFOLIO_V1.json` (verdict:
`NO_SURVIVORS`).

- 40 registered strategy families evaluated (S01-S35, B00-B04) across three gold series:
  `GLOBAL_GOLD_5M_YAHOO`, `GLOBAL_GOLD_15M_REFB`, `GLOBAL_GOLD_1H_REFB` (19,285 bars total).
- **Survivor count: 0.** Explicit rule in the report: "Count NEVER forced" — this is a
  conscious abstention, not a bug.
- 10-point survivor gate table: all gates failed except gate 10 (sample size), where
  S01/S03/S04/S30/S34 passed and S02 was sparse.
- Rejected outright: S01, S02, S03, S04, S30, S34, B01-B04.
- **Data-blocked** (not rejected — this distinction is load-bearing per the report):
  - S17: blocked on missing Open Interest (OI) data.
  - S05-S14, S26: blocked on absent macro data.
  - S15/S16/S18-S25/S27-S29/S31-S33/S35: blocked on absent L2/options/tick flow data.
- The report's own stated next step: real MCX GOLDM data with Volume + OI is required to
  unblock further development. This has not happened as of this audit.

---

## 4. Imported Strategy Bins (BIN_01 / BIN_02 / BIN_03) — Status

Source: `ATS_BIN_01_FINAL_REPORT.md`, `ATS_BIN_02_FINAL_REPORT.md`, `ATS_BIN_03_FINAL_REPORT.md`.

**BIN_01 — infrastructure build.** Verdict `ATS_BIN_01_LIVE_SHADOW_READY`. Nine externally-sourced
strategy files were safely decoded via non-executing static AST analysis (confirmed zero
`eval`/`exec`/`os.system`/`subprocess`/`pickle.loads`), normalized into Pydantic models
(`ats/market/strategy_import/models.py`), and wired into a `ShadowTournamentEngine`
(`ats/market/strategy_import/tournament.py`) driven by a `MarketDataFabric`. All nine are
classified `authority = RESEARCH_ONLY`, `LIVE_COMPATIBLE`. Confirmed strictly isolated from
`PaperBroker` and all broker gateways/order APIs — zero real or paper order placement
capability exists in this path. 7/7 tests pass (`ats/backend/tests/test_strategy_import.py`).
This is real, verifiable infrastructure, not a research claim.

**BIN_02 — prospective (forward) validation, in progress.** Instrument `MCX_FO|GOLDM`,
authority `RESEARCH_ONLY`. Maps the frozen `BIN_S01`-`BIN_S09` IDs to their real source
models:

| BIN ID  | Model                       | Source file         |
| ------- | --------------------------- | ------------------- |
| BIN_S01 | crabel_orb_nr7_model        | `Setup 167%.py`     |
| BIN_S02 | booming_bulls_holy_grail    | `setup 43%21k .sh`  |
| BIN_S03 | booming_bulls_50_absolute   | `setup 45%22k.sh`   |
| BIN_S04 | booming_bulls_max_yield     | `setup 47%21k 1.sh` |
| BIN_S05 | fabio_amt_playbook          | `Setup 48%.py`      |
| BIN_S06 | desiano_break_retest_model  | `Setup 52%.py`      |
| BIN_S07 | apex_chimera_engine         | `Setup 84%.py`      |
| BIN_S08 | unified_master_50pct_engine | `setup 90%.py`      |
| BIN_S09 | crudele_pure_framework      | `Setup155%.py`      |

The report explicitly **refuses to credit the percentage claims baked into these filenames**
("167%", "84%", etc.) as evidence — correct, since those are vendor marketing claims, not
measured outcomes. Only genuine forward `RESOLVED_VALID` outcomes count. As of the report,
the leaderboard shows **all ten strategies (nine imported + native S17) at 0 signals / 0
resolved / 0/20 support / ₹0.00 P&L / `INSUFFICIENT_EVIDENCE`** — S17 specifically flagged
`SHADOW_RUNNING_AWAITING_OI`. Cost-stress tiers are defined (Base ₹40, 1.5x ₹60, 2.0x ₹80
per round-trip) but have nothing to stress-test yet. Promotion governance explicitly forbids
automatic promotion; the stated bar is 20 resolved outcomes + positive net expectancy at
2.0x cost stress + profit factor > 1.30 + drawdown limits, none of which can be evaluated
until real signals accumulate. Verdict: `ATS_BIN_02_PROSPECTIVE_VALIDATION_RUNNING` — this
is an honest "waiting for data" state, not a failure.

**BIN_03 — stub, materially incomplete.** The entire file content is two lines: "# ATS-BIN-03
Final Evidence Report" / "Tournament persistence successfully implemented." There is no
evidence section, no leaderboard, no verdict comparable to BIN_01/02. **This is a real gap**:
whatever BIN_03 was scoped to deliver (persistence layer validation, presumably) has not
been documented to the same standard as its predecessors. Treat BIN_03 as not-yet-audited
work, not as a completed, reviewed deliverable.

---

## 5. Promotion-Ladder Position Summary

Per the ATS Live Eligibility Standard's 7-state ladder
(CANDIDATE → RESEARCH_VALIDATED → SHADOW_ELIGIBLE → SHADOW_ACTIVE → PAPER_ELIGIBLE →
PAPER_ACTIVE → LIVE_MICRO_ELIGIBLE):

| Strategy / family                            | Current state                         | Blocking factor                                                                   |
| -------------------------------------------- | ------------------------------------- | --------------------------------------------------------------------------------- |
| S01, S02, S03, S04, S30, S34 (native)        | REJECTED                              | Failed survivor gates under MCX PIT V3 costs                                      |
| B01-B04 (native)                             | REJECTED                              | Failed survivor gates                                                             |
| S17 (native, OI-dependent)                   | CANDIDATE, SHADOW_RUNNING_AWAITING_OI | No live OI data source                                                            |
| S05-S14, S26 (native)                        | DATA_BLOCKED (not rejected)           | No macro data source                                                              |
| S15/S16/S18-S25/S27-S29/S31-S33/S35 (native) | DATA_BLOCKED (not rejected)           | No L2/options/tick data                                                           |
| BIN_S01-BIN_S09 (imported)                   | CANDIDATE, SHADOW_RUNNING             | 0/20 resolved forward outcomes                                                    |
| **S5 ORB (new, this engagement)**            | **Phase 1 design spec only** (see §6) | Not yet implemented; XAUUSD proxy caps ceiling at CANDIDATE even after validation |

No strategy anywhere in the audited workspace has reached `SHADOW_ACTIVE` or beyond.

---

## 6. New Work This Engagement: S5 Opening Range Breakout

Per user direction, new strategy design work (rather than hardening existing survivors) was
scoped to a single strategy, in depth, rather than three in parallel (S12 Multi-Asset
Lead-Lag and S9 Post-News/Event Drift were deliberately deferred — see §7).

**Deliverable:** `ats/docs/superpowers/specs/2026-09-30-s5-orb-mcx-gold-design.md`
(committed as `6696f69`). This is a Phase 1-3 research design, not an implementation, and
is capped at `CANDIDATE` authority even if fully validated, because:

1. Real MCX GOLDM intraday data does not exist in this workspace; the design uses XAUUSD
   spot forex as an explicit, declared proxy instrument — an instrument mismatch that by
   the Strategy Research Standard's own rules bars promotion past CANDIDATE regardless of
   validation results.
2. No implementation has been written yet — this is a design document only.

Design highlights (see the spec for full detail): 08:20 America/New_York opening-range
anchor; two-stage meta-labeling architecture (Stage 1 breakout scanner, Stage 2
`EXPECTED_NET_EV` meta-classifier); seven explicit dataset-independence constraints direct
response to the user's requirement that the strategy "perform genuinely" rather than fit a
specific dataset; a full offline Purged Walk-Forward CV plan with the Null-Hypothesis
Testing Battery and cost-stress testing at 1.5x/2.0x per the Research Standard.

**Status: awaiting user review of the written spec before any implementation work begins**,
per the brainstorming skill's architectural-path gate.

---

## 7. Deferred Work (explicit stubs, not started)

- **S9 Post-News/Event Drift** — deferred to future work by user's own scope-narrowing
  decision ("Approach C"). No design, no code. Would require a reliable macro/news-event
  timestamp feed, which — per §3 — is exactly the data category STRAT-04 found absent for
  gold.
- **S12 Multi-Asset Lead-Lag** — deferred to future work by the same decision. Would require
  a second correlated instrument feed (e.g., USDINR or DXY) time-aligned to the gold feed
  under the same Four-Clock Causality Contract used elsewhere in the system; no such feed
  currently exists in the workspace for gold.

Both are left as named stubs so a future engagement can pick them up without re-deriving the
scope decision.

---

## 8. Recommendations

1. Resolve the STRAT-02 provenance discrepancy (§2) before citing it again in any report.
2. Resolve or namespace the `sid` collisions in `agents/strategies.py` (§1) before building
   any cross-file strategy dashboard or report that joins on ID.
3. Treat BIN_03 (§4) as undocumented, not completed — do not assume its persistence claims
   are validated until a BIN_03 report matching BIN_01/02's rigor exists.
4. Do not let elapsed time create pressure to promote S17 or the BIN_S01-09 strategies past
   CANDIDATE/SHADOW while OI data and the 20-outcome minimum remain unmet — this is the
   correct, intended behavior of the Four-State Loss Machine and Abstention-as-First-Class
   design, not a stall.
5. For S5 ORB specifically: do not relax the XAUUSD-proxy → CANDIDATE-ceiling rule even if
   validation results look strong. Real MCX GOLDM data (not proxy forex) is a hard
   precondition for any state above CANDIDATE, per the Strategy Research Standard.
