# ATS Implementation Report

**Current status, October 9, 2026:** XAUUSD/MetaTrader specialization and the Step 1
software foundation are retained. Bounded quote research, external authority
development and pure entry/exit diagnostics are implemented and tested. The
small-account S3 observer is physically running on the $1,000 DEMO terminal;
two historical candidate presets have been implemented. Autonomous external
execution remains unrouted and uncommissioned. See the
[current progress report](docs/research/SMALL_ACCOUNT_IMPLEMENTATION_PROGRESS_2026-10-09.md)
for completed work, exact tests, conditional results and remaining acceptance.

The following P4 history predates specialization; it is not current product
acceptance or authorization for external execution.

**Historical status: P4 COMPLETE; INTEGRITY HARDENING PASS DONE.** P4 baseline `220d292`
plus its two CI fixes (`c12d708`) is remotely green (run `36827915472`: all jobs
success except Dependency Review, which is PR-only and skipped on push; PostgreSQL
durability ran 110 tests, none skipped). The hardening commits after it are
verified locally only until their own CI run is recorded below. Items under
[Remaining Work](#remaining-work) are either untouched or explicitly recorded
there as incomplete.

Repo: `D:\Projects\ATS\ats` (branch `main`). Baseline HEAD before this work:
`bd0177b`. Commits made this session are listed under [Commits](#commits); the
last one is the current HEAD.

Axiom that governs every change here: **AI PROPOSES; DETERMINISTIC ATS
AUTHORIZES.** The paper-only invariant (`Literal["A2_PAPER"]`) is untouched.

---

## Commits

| SHA       | Scope                                                                                         |
| --------- | --------------------------------------------------------------------------------------------- |
| `41e4119` | `fix(deps)`: backend runtime dependencies reproducible (`httpx` declared, `uv.lock` repaired) |
| `9754aa9` | `fix(tests,frontend)`: restore collectability of 8 modules, fix conditional hook              |
| `bbc261f` | `ci`: smoke, durability and risk-weighted quality gates                                       |
| `009df58` | `build(frontend)`: lint, formatting and production quality gates                              |
| `28cab3a` | `fix(tests)`: bounded SSE integration read, contract package importable                       |
| `e853ea9` | `fix(runtime)`: synthetic exit authority removed, fail-closed ordering                        |
| `ce00a34` | `docs`: this report, with SHAs and the two open P2 follow-ups                                 |
| `2de1ba1` | `fix(ci)`: four machine-local test failures made honest; token placeholder reshaped           |
| `23eff20` | `docs`: replace the CI caveat with the verified remote result                                 |
| `d5ef50b` | `fix(frontend)`: render only observed market data, never invented state                       |
| `6d0a7c7` | `docs`: record Phase 3 as done-locally, pending push and CI                                   |
| `bc58a8b` | `docs`: record remote verification of frontend honesty phase                                  |
| `74d9daa` | `fix(runtime)`: remove remaining implicit allow authority paths                               |

Each commit was validated on its own (lint, types and its relevant suites pass
at that point, `uv lock --check` clean) so the history can be bisected.

---

## Remote CI verification

### Run `36551337386` (commit `2de1ba1`, 2026-09-29)

Pushed to `origin/main`; **all nine active jobs pass**, `Dependency Review`
skipped as designed.

| Job                              | Result                                                            |
| -------------------------------- | ----------------------------------------------------------------- |
| Lint & Typecheck                 | success (ruff 0, mypy, `pnpm lint` / typecheck / format:check)    |
| Smoke / Governance               | success                                                           |
| Contract Tests                   | success (149 passed)                                              |
| Property Tests                   | success (255 passed)                                              |
| Unit Tests                       | success (1427 passed, 13 skipped)                                 |
| Durability & Faults (PostgreSQL) | success — **110 integration + 37 fault tests, 0 skipped**         |
| Coverage (risk-weighted)         | success (1838 passed, 13 skipped; contracts and kernel gates met) |
| Frontend Tests                   | success (34 tests across 3 packages)                              |
| Secret Scan                      | success (0 findings)                                              |

The durability job is the one that mattered: it provisions a PostgreSQL 16
service, asserts the driver and DSN are really present, then runs
`assert_critical_tests_ran.py` over the JUnit XML and **fails the build** if any
of the nine named safety-critical suites is absent, skipped or errored. It
passed, which converts the local gap recorded below into a verified result:
the 61 integration skips and 8 property/faults skips that cannot run on this
machine **did run in CI, and none of them skipped**.

Two honest caveats about that job, not hedges:

- The 13 skips in Unit Tests are the evidence-outside-the-repo tests described
  under [CI truth](#phase-1---ci-truth-this-session). They skip with a stated
  path; they are not in the critical-suite list and nothing else is.
- Coverage is measured on a Linux runner, so its absolute percentages are not
  comparable to the Windows numbers in the table below. The gates passed.

### Run `36674326430` (commit `6d0a7c7`, 2026-09-30) — Phase 3 verification

Pushed `d5ef50b` + `6d0a7c7`; **all nine active jobs pass**, `Dependency Review`
skipped as designed. This is the run that promotes Phase 3 from
"DONE locally" to "DONE / remotely verified".

| Job                              | Result                                                    |
| -------------------------------- | --------------------------------------------------------- |
| Lint & Typecheck                 | success (ruff 0, mypy strict, eslint, prettier, tsc)      |
| Smoke / Governance               | success (7 passed)                                        |
| Contract Tests                   | success (149 passed)                                      |
| Property Tests                   | success (255 passed)                                      |
| Unit Tests                       | success (1427 passed, 13 skipped)                         |
| Durability & Faults (PostgreSQL) | success — **110 integration + 37 fault tests, 0 skipped** |
| Coverage (risk-weighted)         | success (1838 passed, 13 skipped; gates met)              |
| Frontend Tests                   | success (**38** control-center + 7 api-client + 7 ui)     |
| Secret Scan                      | success (0 findings)                                      |

Durability detail, verified from the job log rather than assumed: Postgres 16
service started, `ATS_TEST_POSTGRES_DSN` populated, `psycopg` imported, real
connection succeeded, and `assert_critical_tests_ran.py` reported **all 9
critical suites executed (147 test cases total)** — none absent, skipped, or
errored. The frontend count (38, up from 20) confirms the new provenance,
data-source, and pill tests ran remotely, not just locally.

### Run `36818969803` (commit `74d9daa`, 2026-10-01) — P2 follow-up closure

Pushed the implicit-allow removal; **all nine active jobs pass**. Counts moved
exactly as the change predicts and nothing else did: Unit Tests 1427 → **1428
passed** (the new omission-denies regression test), Contract Tests 149 → **152
passed** (the three new guards), Coverage 1838 → **1842 passed**, durability
unchanged at **110 integration + 37 fault tests, 0 skipped**, and
`assert_critical_tests_ran.py` again reports **all 9 critical suites executed
(147 test cases total)**. The 13 unit skips are the same stated-path
evidence-outside-the-repo skips.

---

## Verified State (all re-run after the last edit)

| Check                               | Command                                                        | Result                                             |
| ----------------------------------- | -------------------------------------------------------------- | -------------------------------------------------- |
| Python lint                         | `uv run ruff check backend tests`                              | PASS (0 findings)                                  |
| Python types                        | `uv run mypy backend/src`                                      | PASS, 316 files, strict                            |
| Contract + smoke + trading_runtime  | `pytest tests/contract tests/smoke tests/unit/trading_runtime` | **222 passed**                                     |
| + property + faults                 | above plus `tests/property tests/faults`                       | **502 passed, 8 skipped**                          |
| Orchestrator + exit-auth unit suite | `pytest tests/unit/trading_runtime`                            | **63 passed**                                      |
| Integration (API + trading_runtime) | `pytest tests/integration`                                     | **49 passed, 61 skipped** (Postgres-gated)         |
| Backend tests                       | `pytest backend/tests`                                         | **233 passed**                                     |
| Whole-tree collection               | `pytest tests backend/tests --collect-only`                    | **1998 collected, 0 errors** (was 1926 + 8 errors) |
| Frontend lint                       | `pnpm lint` (`eslint .`)                                       | PASS (0 errors, 56 warnings)                       |
| Frontend format                     | `pnpm format:check` (`prettier --check .`)                     | PASS                                               |
| Frontend types                      | `pnpm -r typecheck`                                            | PASS (3 packages)                                  |
| Frontend unit tests                 | `pnpm -r test`                                                 | PASS                                               |
| Production build                    | `pnpm --filter @ats/control-center build`                      | PASS                                               |
| Lockfile                            | `uv lock --check`                                              | PASS                                               |
| CI YAML                             | parsed and validated                                           | 10 jobs                                            |

The 8 + 61 skips are durability tests awaiting a Postgres DSN
(`ATS_TEST_POSTGRES_DSN` is unset locally); `tests/contract` and `tests/smoke`
are fully executed with no skips. They are gated in CI by the critical-suite
assertion below, and [Remote CI verification](#remote-ci-verification-run-36551337386-commit-2de1ba1)
records that they ran there rather than skipped.

---

## Done

### Phase 0 - Repository recovery (committed in prior turns)

- Reconciled 137 dirty paths into ordered commits instead of one mass commit.
- Extended `.gitignore` for artifact/runtime output with explicit negations so
  `ATS_BASELINE_STATUS.md` and this report stay tracked.
- Repaired `uv.lock`: it was missing `uvicorn[standard]==0.38.0` despite being
  declared in `backend/pyproject.toml`. `uv sync --frozen` now passes.
- Rewrote `tests/smoke/test_scope.py` to scan real repository paths via
  `git ls-files -co --exclude-standard -z` with non-vacuous assertion messages.
  The old version could pass while asserting over an empty file set.
- Committed the previously-untracked `api -> console` split, backend `agents/`,
  `ai/`, `datasets/`, `optimization/`, `strategies/`, market live layer,
  observability, execution/paper, all 22 `backend/tests/` files, 16 frontend
  routes, `@ats/ui` primitives, the api-client, the operator launcher shims,
  research harnesses, Playwright acceptance, and `verify_all_features.py`.

### Phase 1 - CI truth (this session)

**CI rewritten** (`.github/workflows/ci.yml`) from 6 jobs to 10 parallel jobs:
`lint-and-typecheck`, `python-smoke`, `python-contract`, `python-unit`,
`python-property`, `python-durability`, `python-coverage`, `frontend-tests`,
`secret-scan`, `dependency-review`.

What makes each one real rather than decorative:

- **`python-durability` runs a Postgres 16 service** and sets
  `ATS_TEST_POSTGRES_DSN`. Previously the 46 durability tests skipped locally
  with no driver in the lockfile, and CI never ran them at all.
- **Skip-proofing via JUnit XML.** Durability suites `importorskip("psycopg")`
  and skip without a DSN, which turns capital double-spend, single-use token
  consumption, durable authority and reconciliation into green skips on any
  misconfiguration. `scripts/ci/assert_critical_tests_ran.py` parses the JUnit
  output and **fails the build** if any of 9 named critical suites is absent,
  skipped, or errored. Entries may only be added, never removed.
- **A "guard the guard" step** verifies `psycopg` imports, the DSN is non-empty,
  and a real `SELECT version()` succeeds, before the suites run.
- **`tests/smoke` is now actually executed.** The governance layer
  (secret/model-artifact scan, ownership manifest, no-live-credential markers)
  was in the repo but never invoked by CI.
- **`-x` removed from every test step.** Fail-fast hides the real failure
  surface behind the first red test; JUnit artifacts record full outcomes.
- **`dependency-review` was dead code.** It was gated on
  `github.event.repository.private == false`, which is permanently false for
  this repo, so the job could never execute. The capability probe is now the
  only gate, with a visible notice when the dependency graph is unavailable.
- **Risk-weighted coverage** rather than one vanity percentage. Coverage is
  collected repo-wide for a complete report, but only the trusted core is
  gated, using thresholds measured locally rather than guessed
  (`contracts` measured 95%, gated at 93; `kernel` measured 84%, gated at 82).
  Thresholds ratchet upward only.
- **Per-test `timeout = 120`** so a hung durability or feed test cannot stall a
  runner to its platform timeout with no diagnostics.
- Job timeouts and an unconditional artifact upload on every test job.

**Frontend quality gates added** (none existed - there was no ESLint or Prettier
config anywhere in the repo):

- `eslint.config.mjs` (ESLint 9 flat config), `.prettierrc.json`
  (`printWidth: 120`), `.prettierignore`, and `lint` / `format` / `format:check`
  scripts.
- ESLint resolved **43 errors to 0**, including `react-hooks/rules-of-hooks`
  finding a genuine conditional-hook defect (below).
- `.prettierignore` excludes generated lockfiles and, deliberately, all
  machine-consumed JSON (`tests/**/*.json`, `data/**/*.json`, market fixtures).
  Those are parsed by tests and some are hashed for provenance: formatting them
  would silently change digests. Style is irrelevant there; bytes are contract.

### Phase 2 - Authorization escape hatches (committed in `e853ea9`)

The runtime could reduce a position on its own authority. `_execute_exit` built
the `ExitIntent` and `Position` the paper broker asked for (hardcoding a
position identity), then passed a literal `ALLOW` as the authorization to
`submit_exit`. Separately, `PaperBrokerAdapter.seed_fill` let the autonomous
path write its own settlement, and every entry `OrderIntent` was bound to
placeholder identities minted on the spot. One defect, three shapes: the
deterministic layer manufacturing the evidence that is supposed to authorize it.

**Exit authority became a seam**
(`backend/src/ats/trading_runtime/exit_authorization.py`):

- `ExitAuthorizationRequest` carries the real position key, a fresh
  `exit_intent_id`, instrument, quantity, reason and reason codes.
- `ExitAuthorizationResult.allows_exit()` is true only when the decision is
  `ALLOW` **and** both artifacts are present. `ALLOW` without artifacts reports
  `POSITION_BINDING` rather than being satisfied by improvising them.
- `UnavailableExitAuthorization` is the default and answers `UNKNOWN`. Nothing
  is wired implicitly: production refuses until an operator configures an
  authority. This is the constraint the original brief named -
  `ReductionAuthorityService` needs a Postgres `TransactionManager` and cannot
  be constructed inside the in-memory orchestrator, so
  `ReductionAuthorityExitAuthorization` adapts that durable path and folds every
  failure into a non-allowing result.

**In `_execute_exit`:**

- The provider runs before any exit state is touched. A refusal increments the
  new `exit_authorization_refused` counter and emits a `BLOCKED` decision, and
  never reaches `emergency_exits`, `on_exit` or `submit_exit`.
- `_snapshot_position_id` and `_position_snapshot` are deleted, along with the
  fabricated `risk_decision_id` and `autonomy_token_id` UUIDs.
- A supplied snapshot whose instrument or quantity no longer matches the
  position being reduced is refused as stale.
- An authority that raises is mapped to `UNKNOWN` and recorded as a refusal: it
  neither escapes into shutdown nor reads as permission.

**Entry binding (P2.3):** new `OrderIntentBinding` records policy, forecast,
risk-decision, advisory and token identity plus the risk economics, which are
now **supplied** rather than derived. `submit_order` refuses an unbound entry
before any broker state exists instead of minting `uuid(int=1..5)` and a
`lot_size * tick_size * 10` loss figure. Exits are unaffected - they carry an
authoritative `ExitIntent`/`Position` and never build an `OrderIntent`. The
orchestrator's `IntentBindingProvider` defaults to `None`, so a candidate with
no upstream evidence submits nothing.

**Fill seeding:** `PaperBrokerAdapter.seed_fill` is gone; integration tests use
`tests/integration/trading_runtime/paper_fill_seed.py`, and a guard asserts no
production module imports it.

**Test authority is explicit (P2.5):** `build_orchestrator` threads
`intent_binding_provider` (default `None`), so entry tests pass
`allow_all_with_binding` and exit tests pass a named double - or nothing at all.

**Guards and failure semantics:**

- `tests/contract/trading_runtime/test_exit_authority_boundary.py` asserts no
  literal `ALLOW` as exit authorization, no fabricated identity helpers, no
  `uuid(int=N)` or derived risk economics in the broker, no manual fill
  primitive, no permissive default binding, plus fail-closed behaviour for an
  absent provider and an artifact-less `ALLOW`.
- `tests/unit/trading_runtime/test_exit_authorization_failures.py` covers
  refusal from seven directions - `DENY`, `UNKNOWN`, a throwing provider,
  `ALLOW` without artifacts, no provider configured, a stale snapshot, and the
  control where a coherent snapshot does close - asserting each leaves the
  position open, records the refusal, does not count an emergency exit, and
  never reports `CLOSED`.

`tests/unit/trading_runtime` went from 52 to **62** tests; the phase is verified
at 62 passed with ruff 0 and mypy strict clean.

**P2 follow-ups closed in `74d9daa` (remotely verified in `36818969803`):**

- `NoopAuthorityService.try_reserve_for_candidate` answers UNKNOWN with
  `AUTHORITY_UNAVAILABLE` instead of ALLOW with `NOOP_ALLOW`. The default
  capital authority performs no reservation and authorizes nothing.
- `request_exit` without a durable reduction authority is always listed as
  unauthorized with `EXIT_EVIDENCE_REQUIRED`; the `authorized = isinstance(...)`
  derivation is gone. The `_try_authority_for_signal` early return stays as a
  documented statement (no reservation attempted, not granted): reservation is
  durable-capital scope, and paper-path entry gating is owned by the
  orchestrator's fail-closed provider.
- `build_orchestrator` maps an omitted `authorization_provider` to the
  orchestrator's own fail-closed DENY default; every test needing entries now
  passes `allow_all` explicitly. `test_omitted_authorization_provider_denies_by_default`
  proves omission refuses, and the contract guards forbid `or allow_all`
  fallbacks, `allow_all` in builder defaults, any ALLOW inside
  `NoopAuthorityService`, and any `authorized = isinstance` derivation —
  plus a behavioural proof that a default runtime lists exits unauthorized.

### Phase 3 - Frontend honesty (committed in `d5ef50b`, remotely verified in `36674326430`)

The control center presented several things as measured that were not, and
every one of them erred in the optimistic direction. This phase removes the
fabrications rather than relabeling them.

**Chart provenance (`lib/provenance.ts`, new):**

- `chartBarsFromCandles` keeps ONLY bars whose open, high, low and close are
  all present and numeric. A bar missing any leg is skipped and counted, never
  interpolated. Bars with unknown volume are kept with `volume: null` and
  render as gaps.
- `evaluateChartProvenance` decides what the chart may claim from the series
  envelope, feed health, quote state and transport, failing closed: no series
  or no bars means NO_FEED/UNKNOWN, a dropped transport means frozen STALE
  history labeled as such, and LIVE requires a live series plus a live (or
  absent) health signal. The requested source travels through as a label.

**LiveChart renders observed bars or an honest empty state:**

- The 95-bar `patternDeltas` generator and the 1 Hz `Math.random()` pulse
  (including its footprint-store writes) are deleted, with the last-bar
  overwrite against a preset base price.
- VWAP skips unknown-volume bars instead of assuming 1200; the footprint sync
  passes volume through instead of defaulting it.
- Price, change, OHLC legend, measure tool, ticket and card all handle "no
  observed bars" with "—" rather than preset prices. A provenance banner shows
  LIVE/STALE/NO FEED with bar counts, authority class, reason codes and
  skipped-bar counts.
- The POSITIONS/ORDERS tabs' static cards are labeled illustrative samples;
  the ORDERS "FILLED" ticket no longer claims a fill. Footprint memory reads
  "~KB (est.)" and latency reads "not measured".

**Shell honesty:**

- `ShellWrapper` maps a failed control-plane fetch to UNKNOWN instead of READY.
- The header pill derives from system state plus stream state (LIVE READY only
  when both agree; READY · FEED DOWN; NOT LIVE; CHECKING).
- The data-source selector is backed by a `DataSourceProvider` context
  (`lib/dataSource.tsx`) with typed values, labeled as a request because the
  backend exposes no per-source selection; actual feed state comes from chart
  provenance.

**Hook and panels:**

- `useMarketFeed` keeps the full candle-series envelope and maps the compact
  socket quote through: quantities and age pass through or stay null (age
  computed from exchange timestamps), state mirrors the server's feed-health
  classification defaulting to UNKNOWN. Quantity 1, age 50 ms and hardcoded
  LIVE are gone.
- Dashboard wires data it already fetched: registry-count strategies chip,
  "—"/"unknown" instead of 75420.0 / MCX_REGULAR / GOLDM FUT 05 OCT 26 /
  FEED_ACTIVE, market-open no longer defaults to true, and system/readiness/
  autonomy rows render fetched values.

**Tests:** `lib/__tests__/provenance.test.ts` (9 cases), `lib/__tests__/dataSource.test.tsx`
(3 cases), six new shell cases covering every pill state plus the selector.
Control-center suite is **38 passed** across 4 files; typecheck clean on all 3
packages; eslint 0 errors (56 warnings, down from 57); prettier clean;
production build succeeds.

**Deliberately out of scope:** the LiveChart decomposition into `chart360/`
modules (charter item 6), the two ATR definitions, unimplemented drawing tools,
and the `AICopilotPanel` backend URL.

**Status: DONE / remotely verified** (run `36674326430`, 2026-09-30) — the
numbers above are local; the remote run confirms them, including the 18 new
frontend tests (control-center 20 → 38). No push is pending for this phase.

### Latent defects found and fixed (not in any planned scope)

1. **`httpx` was an undeclared runtime dependency.**
   `backend/src/ats/ai/laya_bridge.py:28` imports it, but no manifest declared
   it. It only worked because a stale local environment happened to have it. A
   clean `uv sync --frozen` removed it and **5 contract tests began failing**.
   Those tests (`tests/contract/api/test_console_boundary.py`) were untracked
   until Phase 0, so CI had never run them - a fresh clone would have shipped
   red. Fixed by adding `httpx==0.28.1` to `backend` dependencies. This is
   exactly why frozen lockfile verification had to be part of CI.

2. **Conditional React hook in `useSse.tsx`.**
   `useSse()` called `useContext`, then reached an early `return context` before
   calling `useLocalSse()` - ESLint caught it as
   `rules-of-hooks: called conditionally`. Depending on whether an `SseProvider`
   was mounted, the number of hooks per render changed, corrupting hook order.
   Fixed by always calling both hooks and gating only the _effect_ behind an
   `enabled` argument, so the local instance stays idle when a provider already
   owns the connection. Behaviour preserved, no second SSE connection opened.

3. **8 test modules were silently uncollectable.**
   `__init__.py` placement was inconsistent, so `tests/integration/trading_runtime`
   and `tests/unit/trading_runtime` both collapsed onto the module name
   `trading_runtime`. Whichever was selected second failed to import with
   `No module named 'trading_runtime.test_startup'`. The victim modules were
   orchestrator, startup, shutdown, reconciliation, compound failures, forward
   validation, autonomous acceptance and broker autofill - **precisely the
   suites that cover the authorization path in Phase 2**. They had never run.
   Fixed by making `tests/`, `tests/unit/` and `tests/integration/` packages,
   which yields unique fully-qualified names and matches the repo's existing
   absolute `from tests.*` import convention. **52 previously-dead tests now
   run and pass.**

   Note on approach: a full `__init__.py` chain across all 108 test directories
   was tried first and rejected - it triggered a pytest conftest
   double-registration for two integration modules. The 3-file fix is strictly
   better than both the baseline and that attempt (1998 collected / 0 errors
   today versus 1978 at the time of the fix, 1926 + 8 errors before it).

4. **`pnpm -r test --if-present` cannot work here.** pnpm 11 forwards unknown
   flags to the script, and vitest rejects `--if-present` with
   `CACError: Unknown option`. CI now calls `pnpm -r test`; all three packages
   define a `test` script.

5. **`eslint-plugin-react-hooks` v6 exports `configs.recommended` as a flat
   config _array_.** Spreading `...configs.recommended.rules` is undefined, so
   the rules silently vanish and lint reports nothing. Declared
   `rules-of-hooks` and `exhaustive-deps` explicitly, with a comment recording
   why. Verified via `--print-config` that they are now active.

6. **Removed a `@ts-ignore` that was masking nothing** in
   `app/api/jev/route.ts` (a `@ts-expect-error` conversion proved the directive
   was unused), removed a dead `imbCount` accumulator in `lib/footprint.ts`, and
   removed an `eslint-disable` comment referencing a rule that does not exist in
   this configuration.

7. **`tests/unit/api/test_stream.py::test_sse_connected_reader_preserves_provider_order`
   could never pass, on any machine.** `iter_sse` has no natural end: after the
   snapshot it heartbeats until the client disconnects, and the stub returned
   `False` forever, so the test ran to the 120 s `pytest-timeout` and was killed
   before reaching a single assertion. It also asserted `len(rendered) == 1`,
   which no terminating stream can satisfy, because `": connected"` is always
   yielded after the snapshot. Only visible once CI ran `tests/unit` on Linux.
   Fixed by making the stub count polls and disconnect on request, and by
   asserting the thing the test is actually named for: the provider's event
   first, then the channel confirmation. This is the second instance of the same
   unbounded-SSE defect that `28cab3a` fixed in the integration suite.

8. **Three test modules asserted on paths outside the repository.**
   `backend/tests/test_strategy_import.py` reads
   `D:\Projects\ATS\ATS trade data\strategy bins` and
   `backend/tests/test_paper_tournament.py` audits
   `D:\Projects\ATS\evidence\paper_sessions\PT-20260924-075030_results.csv`.
   All four affected tests pass on this machine and cannot pass on any clone.
   They now skip with the path and reason stated. Worth being precise about the
   asymmetry: only the tests that read those directories were marked — the other
   five in the strategy module build their adapters from code and still run
   everywhere — and the security-critical durability suites are in a different
   registry entirely, gated by `assert_critical_tests_ran.py`.

9. **A `.gitleaks.toml` containing only an `[allowlist]` silently disables the
   entire secret scan.** This is the obvious fix for a false-positive finding
   and it is a trap. gitleaks treats a supplied config as the _complete_
   ruleset, so a config with no `[[rules]]` detects nothing at all. Measured
   with gitleaks 8.30.1 over full history: **15 findings with no config, 0 with
   an allowlist-only config, and 0 with an allowlist whose regex cannot match
   anything.** The distinction that proves it is that last number — a
   well-meaning allowlist and a nonsense one behave identically, which is the
   signature of a rule set that is switched off rather than a rule that is
   satisfied. Nothing was allowlisted. The finding itself was a fabricated
   autonomy token id (`TOK-0924-87A1BC`, entropy 3.77) in the canned
   governance overview payload; the placeholders are now `sample-token-consumed`
   / `sample-token-issued`, which says what they are and has no credential
   shape. A scan that passes because its rules were turned off is worse than one
   that is red.

---

## Remaining Work

Ordered so that safety work lands before ergonomics. Each item names the file
evidence already gathered.

### P2 - Authorization escape hatches (DONE, follow-ups closed in `74d9daa`)

Completed in `e853ea9` and documented under
[Phase 2](#phase-2---authorization-escape-hatches-committed-in-e853ea9):
exit-authorization seam with a fail-closed default, removal of
`_snapshot_position_id` / `_position_snapshot` / the literal `ALLOW`,
`seed_fill` moved out of the production adapter, placeholder identity minting in
`_build_order_intent` replaced by an explicit `OrderIntentBinding`, and
source-scanning guards plus seven-direction refusal tests.

Both recorded follow-ups are now closed (see the P2 closure note in Done,
remotely verified in `36818969803`): entry authority is explicit in every
test (omission means DENY), and the default capital authority grants nothing.

### P3/P5 - Frontend honesty (DONE, remotely verified in `36674326430`)

Completed and documented under
[Phase 3](#phase-3---frontend-honesty-committed-in-d5ef50b-remotely-verified-in-36674326430):
synthetic chart history and random-walk pulse deleted, quote fields passed
through instead of hardcoded, shell pill and data-source selector honest,
dashboard wired to fetched data, 18 new frontend tests (control-center 20 →
38, confirmed in the remote log).

Left over for a later chart pass (charter item 6, not started):

- `LiveChart.tsx` is still one large file (~3,500 lines) — decomposition into
  `chart360/` modules with unit tests for the indicator math.
- Two contradictory ATR definitions (`computeAtr` SMA vs Wilder inside
  `computeSuperTrend`) still need unifying.
- 5 of 7 declared drawing tools remain unimplemented.
- `AICopilotPanel.tsx:38` still hardcodes `http://127.0.0.1:8000/v1/ai/query`,
  bypassing the proxy.

### P4 - Agent management surface (§23) — DONE locally, unpushed

**Status:** backend and frontend implemented; validated locally; NOT pushed;
REMOTE CI NOT RUN for these commits.

**Design decision:** the existing `agents/` modules are the strategy-persona
playground (principals, lots, trade ledgers). Managed agents are a separate,
proposal-only administrative domain: `backend/src/ats/agents/managed.py` +
`managed_router.py` at `/v1/agents/managed`. The playground's 39 routes and its
3,500-line `/agents` page are untouched; the two are linked, not merged.

#### Managed agent backend

- Domain: `ManagedAgent`, append-only `AgentConfigVersion`, `AgentRun` bound to
  the exact config version that produced it. JSON-file store (atomic temp-file +
  `os.replace`) — an interim persistence choice, not Postgres.
- Boundary: the capability vocabulary is a closed allowlist of 11 research /
  proposal verbs; data and research scopes are closed too. Financial authority
  has no member, so it is unrepresentable rather than rejected after parsing.
  Contract: `tests/contract/agents/test_managed_agent_boundary.py` (4 tests).
- Credentials: only an env-var NAME (`credential_ref`, `^[A-Z][A-Z0-9_]{1,63}$`)
  is accepted and persisted; secret-looking values are rejected.
- Lifecycle: new agents are DISABLED; enable/disable never bumps the version;
  edit appends a version; duplicate = new id, fresh v1, DISABLED, no runs copied;
  DELETE archives by default; hard delete needs `hard=true` AND `confirm=true`
  AND no runs AND a single config version (all server-side). Disabled/archived
  agents cannot start runs; in-flight runs are not cancelled. Audit goes through
  the activity log; the closed 24-entry domain event registry is untouched.
- Added in this continuation (focused fix commit): `GET /v1/agents/managed/schema`
  serves the canonical vocabularies so no client keeps a second copy; and an
  unreadable store file is now quarantined (`managed.json.corrupt-<ts>`) instead
  of loading empty and being overwritten by the next save.
- Known limits (verified by reading, not changed): no cross-request lock, so
  concurrent `PATCH`es could in principle assign a duplicate version number;
  `max_concurrency` is stored but not enforced because runs are only _recorded_;
  run `error` text is stored as given (length-bounded, not secret-scrubbed).
  Fine for the interim JSON store; revisit with a database.

#### Managed agent frontend

- api-client: typed methods for every existing managed route; vocabularies stay
  plain strings sourced from `/schema`; no execution-shaped method exists
  (asserted by test). `parseError` now also keeps FastAPI `{detail}` messages.
- `/agents/managed`: list (search, status/type filters, archived toggle,
  empty/error states), 8-step Add Agent wizard (identity, provider/model with
  credential-NAME-only field, responsibilities, data access, research scope,
  capabilities, runtime limits, review with the safety statement; creates
  DISABLED), and `/agents/managed/[id]` detail (config, exact version, runs with
  the version they ran under, version history, edit-as-new-version, enable/
  disable, duplicate, archive with explanatory confirmation, and a secondary
  "advanced" hard delete whose refusal reason comes from the server).
- Step 3 has no separate "role/purpose" field: the backend only has
  `description` and `system_instructions`, so none was invented.
- Nav: "Managed Agents" entry; active-link logic now picks the most specific
  entry so `/agents` no longer also highlights on `/agents/managed`.

#### Verified locally (this continuation, after the last edit)

| Check                                                        | Result                                                                             |
| ------------------------------------------------------------ | ---------------------------------------------------------------------------------- |
| `ruff check backend tests`                                   | PASS (0 findings)                                                                  |
| `mypy backend/src` (strict)                                  | PASS (318 files)                                                                   |
| `pytest tests/contract backend/tests/test_managed_agents.py` | PASS 174 (156 contract + 18 managed)                                               |
| `pytest tests backend/tests --collect-only`                  | PASS, 2024 collected (full suite NOT run)                                          |
| `pnpm -r test`                                               | PASS (api-client 10, ui 7, control-center 57)                                      |
| `pnpm -r typecheck`                                          | PASS                                                                               |
| `pnpm lint`                                                  | PASS (0 errors, 56 pre-existing warnings, unchanged)                               |
| `pnpm --filter @ats/control-center build`                    | PASS (both new routes emitted)                                                     |
| `pnpm format:check`                                          | FAIL on `.governor/RESUME.auto.md` only — gitignored tool output, not repo content |

The full backend suite (`pytest tests backend/tests`) was **not** executed here,
only collected; run it (and remote CI) before relying on "all green".

### Integrity hardening pass (after P4)

| Area                      | Change                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 | Evidence                                      |
| ------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------- |
| Remote CI                 | `220d292` failed two jobs: gitleaks flagged a deliberately fake secret in a managed-agent test, and a 5 ms wall-clock latency test failed under coverage tracing. Fixed in `c12d708` (fake secret built at runtime + fingerprint-scoped `.gitleaksignore` for the one pushed commit; latency bound skipped only under coverage, still enforced by the plain unit job).                                                                                                                 | run `36827915472` green on `c12d708`          |
| Strategy identity         | Root cause: registry/lab lookups reduced `S02_TSMOM` / `S02_MICRO_TICK` (and `S03_*`) to the prefix `S02`, which is also the registry's own STRAT-04 `S02`. The live-performance update also mutated a shared record list before failing on a frozen model, so one strategy's record could pollute another's. Now exact full-ID lookup via `ats/strategies/identity.py`; bare prefixes fail closed; aliases must be explicit (none exist); update is copy-on-write. No ID was renamed. | `backend/tests/test_strategy_identity.py` (8) |
| Managed-agent concurrency | `RLock` over every store operation (same-process threads); optional `expected_version` -> HTTP 409, UI says to reload and does not retry. Supported envelope is one process; no cross-process file lock.                                                                                                                                                                                                                                                                               | 12-thread race and 2-writer tests             |
| `max_concurrency`         | Enforced at run admission (`POST .../runs`), the only run boundary this domain has; no scheduler was invented. A finishing run no longer reports IDLE while others run, nor re-activates a disabled agent. `timeout_s` remains **not enforced** (no executor); the wizard says so.                                                                                                                                                                                                     | tests in `test_managed_agents.py`             |
| Run-error scrubbing       | `ats/agents/redaction.py` removes credential env values, bearer/basic tokens, URL passwords, `key=value` secrets and common token shapes before persistence.                                                                                                                                                                                                                                                                                                                           | persisted store, API, logs asserted           |
| Corrupt JSON              | `ats/persistence/json_files.py`: an unreadable or wrong-schema store is moved aside intact and saves are blocked if it cannot be. Applied to the managed-agent store, the Upstox trade ledger and the agent roster. `deployment.py` (read-only report, falls back to HOLD) needed no change.                                                                                                                                                                                           | `test_json_store_integrity.py`                |
| CORS                      | Wildcard + credentials replaced by an explicit allowlist (`ats/console/cors.py`): local control-center origins by default, `ATS_CORS_ORIGINS` override, wildcard/malformed values abort startup.                                                                                                                                                                                                                                                                                       | `test_console_cors.py`                        |
| Ownership                 | `ownership.json` now covers agents, ai, console, datasets, governance, optimization, persistence, strategies, trading_runtime. Contract test requires exactly one owner per production file and fails on unknown packages. Stream letters are architecture metadata, not CODEOWNERS.                                                                                                                                                                                                   | `tests/contract/architecture`                 |

**Lost data (disclosure).** `data/agents/upstox_live_trades_ledger.json` was found
corrupt (JSON error near line 10961). During this session it became `[]`: the file is
gitignored, no backup exists, and the original bytes are **unrecoverable**. The
overwrite-after-corrupt-load defect is what allowed it; whether a test or script run in
this session or another process wrote the empty file cannot be established.

**Open: test-isolation leak.** Running backend tests still rewrites the real
`data/agents/upstox_live_trades_ledger.json` and `agents_config.json`
(bisected to the agent playground/worker/managed-agent test files). An autouse fixture
redirecting the path constants and singletons was tried and abandoned: it broke
`test_history_wipe_and_fresh_start` and did not stop the writes. With quarantine in
place a corrupt real file is now preserved instead of overwritten, but the leak itself is
unfixed.

**Not done / still limited:** no executor enforces `timeout_s`; the managed-agent JSON
store has no cross-process lock; strategy IDs were not renamed; the ledger tests and
frontend do not cover every API response for full-ID preservation.

### Parallel strategy research (not P4 work)

- `docs/superpowers/specs/2026-09-30-s5-orb-mcx-gold-design.md` — S5 Opening Range
  Breakout **design only**. Research instrument is XAUUSD spot as a _proxy_; no
  MCX intraday data is claimed; maximum outcome is CANDIDATE. Not implemented;
  awaiting explicit user GO.
- `docs/research/MCX_GOLD_STRATEGY_READINESS_AUDIT.md` — no workspace strategy is
  promoted beyond CANDIDATE / RESEARCH_ONLY.
- Both were reformatted by Prettier only (semantic no-op).

#### Outstanding research findings (NOT fixed)

- **S02 / S03 prefix collision.** `agents/strategies.py` defines `S02_TSMOM` and
  `S02_MICRO_TICK`, `S03_DONCHIAN_ATR` and `S03_GAP_FILL`. Full IDs are distinct,
  but `strategy_registry_service.py` (`update_live_performance`,
  `get_strategy_scores_dict`) and `strategies/lab_service.py` fall back to the
  `split("_")[0]` prefix, so one strategy's score or live performance can be
  attributed to the other. The IDs are referenced in ~12 files (paper tournament,
  runtime router, optimization worker, several pages and tests), so a rename is
  a migration, not a fix. Safe remediation: stop the prefix fallback first
  (exact-ID lookups only), then decide on renames with a migration map.
- **STRAT-04 / STRAT-02 provenance.** STRAT-04's "20 strategies rejected under
  STRAT-02" corroboration is unverified: the only STRAT-02 artifact found is a
  hash freeze, not a rejection tournament. No evidence has been created.
- **BIN_03 report incomplete.** `ATS_BIN_03_FINAL_REPORT.md` is a two-line stub.
  Sibling artifacts sit in the workspace root (outside this repo, untracked) but are
  thin: three CSVs of ~11 lines each, two header-only CSVs (complementarity,
  session ledger) and a two-line cost audit. Whether they suffice to reconstruct
  a report is undetermined. None was written and no results were synthesized.

### Later phases (not started, not estimated)

- **Replay harness** (§12) and **evidence chain** (§13).
- **Property-based testing** expansion - `kernel/reduction.py` sits at **58%
  coverage**, the weakest module in the trusted core; `kernel/risk.py` is 71%
  and `kernel/policy.py` 78%. These need real tests, not threshold relief.
- **Frontend wiring/integration** for agents and replay.
- **`console/app.py:177`** - `allow_origins=["*"]` should be tightened to an
  explicit origin list.
- **`ownership.json` + `.github/CODEOWNERS`** are stale and unenforced.
- **Operator scripts** carry hardcoded `C:\Users\subha\.gemini` screenshot
  paths; make them configurable.
- **Full `tests/unit` suite** still takes >900 s serially. Parallelism was
  deliberately **not** introduced (xdist changes fixture/DB semantics and was
  not verified safe). Revisit this only with a correctness argument.
- Raise the coverage gates once `reduction.py` / `risk.py` are covered.

---

## Explicitly NOT done (do not mistake these for oversights)

- **No live broker.** `Literal["A2_PAPER"]` is unchanged; no `LIVE` mode
  introduced.
- **No AI authorization path, no frontend authority.** The console remains a
  read-only proposal surface (now enforced by executed tests).
- **No UNKNOWN-to-ALLOW fallback** anywhere.
- **No invented data.** Nothing in test fixtures or manifests was fabricated to
  make a number move; the two skip-prone durability suites remain honestly
  skipped locally and honestly gated in CI.
- **No weakened token semantics, no blind retry.**
- **No throwaway files**, no `git add -A`, no `.gitignore` churn to hide
  artifacts. Every commit is scoped and named in [Commits](#commits); nothing
  was pushed, so CI has not yet confirmed the remote results.
- Local Node is v26.4.0 against a pinned v24.19.0; this produces a warning only
  and does not affect any result above. CI pins 24.19.0.

## Verification after the hardening pass (local)

PASSED: `ruff check backend tests`; `mypy backend/src` (322 files); `pytest tests/contract` (160);
`pytest backend/tests` (288); `pnpm format:check`; `pnpm lint` (0 errors, 56 pre-existing
warnings); `pnpm -r typecheck`; `pnpm -r test` (10 + 7 + 58); control-center build.
COLLECTED ONLY: `pytest tests backend/tests --collect-only` = 2,065 tests.
NOT RUN LOCALLY: `tests/unit`, `tests/property`, `tests/smoke` in full and the PostgreSQL
durability suite (CI runs them).

## 2026-10-07: XAUUSD specialization and MetaTrader Step 1 checkpoint

**Current capability: Step 1 software implemented and locally green; physical
acceptance incomplete.** This section supersedes earlier market/provider/runtime
claims in this historical implementation log. AI proposes; deterministic ATS
and portfolio authority authorize. External execution has not been implemented.

- Removed the old provider/Indian-derivatives stack, related active data and derived
  performance, unsafe persona execution playground, obsolete routes and dependencies.
  The pre-deletion inventory and local recovery marker remain available.
- Canonical XAUUSD observations, MetaTrader adapters, account-separated journals and
  fabric, immutable CSV/Parquet ingestion, proxy footprint provenance and XAUUSD
  research-only definitions replace the removed product paths.
- Added transactional multi-account registry, Windows DPAPI credentials, bounded
  spawned MT5 account workers, verified identity/profile isolation, account monitoring
  and explicit connection/consent UI. Demo/live share connection architecture;
  LIVE is not rejected for its mode. MT4 authenticated accounts are NOT_CONFIGURED.
- Account consent reports EXTERNAL_ROUTING_NOT_IMPLEMENTED. Restart/reconnect/error
  revoke consent. Risk profiles and full broker reconciliation remain Step 3 work.
- Fixed cross-thread SSE delivery, journal-before-fanout admission, future/bar timing,
  standalone shutdown and independent account failure. No terminal order surface exists.
- Unified chart/research Wilder ATR and removed unobserved-volume VWAP fallback.
  All surviving strategy evidence is empty and RESEARCH_ONLY; S5 remains DESIGN with
  its fifteen unresolved review topics. Heuristic confidence is not probability.
- Pure kernel, portfolio, persistence and deterministic hashing source are unchanged.
  The domain venue/segment literals changed to OTC/SPOT_METAL. Fixture metadata
  changes required explicit golden rebaselines; hash algorithms/gates were preserved.

Final local checks: **1,511 Python tests passed, 0 failed, 0 skipped** with PostgreSQL;
1,511 tests collected; Ruff green; strict mypy green (231 modules); contracts coverage
95% (gate 93%), kernel 86% (gate 82%). Frontend: 10 API-client + 7 UI + 41 control-center
checks passed; format/types/lint/build passed (lint: 0 errors, 3 existing copilot warnings).
`uv lock --check`, `uv sync --frozen` and `pnpm install --frozen-lockfile` passed.
A fresh isolated frozen Python environment also installed/imported the pinned SDK and
Parquet dependencies. CI now checks tracked-file cleanliness after test/build gates.
Remote exact-HEAD CI is recorded separately in the generated boundary report.

Actual terminal: pinned SDK imports, IPC initializes and an authenticated DEMO account
supplies XAUUSD metadata/quotes. Its tick epoch is approximately three hours ahead of
verified UTC; the connector rejects it. Real concurrent account-worker acceptance has
not been demonstrated. No orders were sent; no strategy edge or calibration is claimed.
At that checkpoint Step 2 had not started. The newer October 8 request explicitly
authorized proceeding with Steps 2–4; physical acceptance gaps remain unresolved.

Architecture: [specialization](docs/architecture/XAUUSD_MT5_SPECIALIZATION.md),
[account foundation](docs/architecture/METATRADER_MULTI_ACCOUNT_EXECUTION.md), and
[shorter remaining execution plan](docs/architecture/ATS_REMAINING_EXECUTION_PLAN.md).
Generated checkpoint reports: ATS_XAUUSD_MT5_MIGRATION_REPORT.md,
ATS_METATRADER_STEP1_REPORT.md and ATS_MT5_00_ENVIRONMENT_REPORT.md.

CI portability correction: preserved raw hashed fixture bytes across Git checkouts and guarded the DPAPI loader for Linux typing. The initial remote run exposed these defects; gates were retained. Final cleanup also removed an obsolete forward-readiness report and specialized the synthetic benchmark. See the generated Step 1 report for final exact-HEAD CI.

## October 8, 2026 — Strategy OS foundation checkpoint

**Steps 2–4 are not complete.** Step 2 storage/schema/UI foundations are implemented;
the supervised research worker, scheduling and independent evidence verifier are
not wired. Steps 3 and 4 remain unimplemented. Production remains paper-only;
execution connection consent still does not route orders.

Implemented: 17 frozen XAU lineage allocations; transactional never-reused IDs;
immutable hashed versions and optimistic conflicts; pause/retire; fail-closed
promotion/evidence writes; generated strategy workspace; canonical API and shared
compatibility registry projection; queue storage with exact job provenance,
idempotency, single claims, nonces, result hashes and explicit interrupted recovery;
strict signal schema with UNKNOWN empirical probability; ten proposal-only templates;
Strategies/Agents UI and corrected registry client types. Fixed a SQLite handle
leak found on Windows. No trusted-core changes or broker orders.

Local full suite: 1,522 passed, 0 failed, 0 skipped, PostgreSQL active. Ruff and
strict mypy pass (237 modules). Frontend tests: 58 passed; build, lint (three existing
copilot warnings), format and type checks pass. Frozen Python/Node installs pass;
orphan local metadata was preserved outside the virtualenv, then `uv pip check`
reported all installed packages compatible. Remote exact-HEAD CI is recorded in
the generated boundary report; do not infer it from the prior Step 1 run.

Detailed status: [system report](docs/architecture/ATS_SYSTEM_STATUS_2026-10-08.md),
[Strategy OS](docs/architecture/STRATEGY_OPERATING_SYSTEM.md),
[agent research](docs/architecture/AGENT_RESEARCH_SYSTEM.md), and the updated
[remaining execution plan](docs/architecture/ATS_REMAINING_EXECUTION_PLAN.md).
Next integration: one bounded supervised worker over the existing research engine,
verified dataset/recipe/agent binding and enforced scheduling/resource bounds.
