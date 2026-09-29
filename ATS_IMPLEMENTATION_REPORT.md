# ATS Implementation Report

**Status: IN PROGRESS.** Covers Phases 0-1, the Phase 2 authorization work, and
several latent defects found and fixed along the way. Items under
[Remaining Work](#remaining-work) are either untouched or explicitly recorded
there as incomplete. This document is extended as phases land; it is not final
until every item under Remaining Work is either DONE or explicitly descoped in
writing.

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

Each commit was validated on its own (lint, types and its relevant suites pass
at that point, `uv lock --check` clean) so the history can be bisected.

**Remote status: AWAITING REMOTE CI VERIFICATION.** All results below are local.
The Postgres-backed durability suites (61 skips under `tests/integration`, 8
under `tests/property` + `tests/faults`) cannot run here and must be confirmed
by the `python-durability` job. `tests/contract` and `tests/smoke` have **zero**
skips.

---

## Verified State (all re-run after the last edit)

| Check                               | Command                                                        | Result                                             |
| ----------------------------------- | -------------------------------------------------------------- | -------------------------------------------------- |
| Python lint                         | `uv run ruff check backend tests`                              | PASS (0 findings)                                  |
| Python types                        | `uv run mypy backend/src`                                      | PASS, 316 files, strict                            |
| Contract + smoke + trading_runtime  | `pytest tests/contract tests/smoke tests/unit/trading_runtime` | **218 passed**                                     |
| + property + faults                 | above plus `tests/property tests/faults`                       | **502 passed, 8 skipped**                          |
| Orchestrator + exit-auth unit suite | `pytest tests/unit/trading_runtime`                            | **62 passed**                                      |
| Integration (API + trading_runtime) | `pytest tests/integration`                                     | **49 passed, 61 skipped** (Postgres-gated)         |
| Backend tests                       | `pytest backend/tests`                                         | **233 passed**                                     |
| Whole-tree collection               | `pytest tests backend/tests --collect-only`                    | **1998 collected, 0 errors** (was 1926 + 8 errors) |
| Frontend lint                       | `pnpm lint` (`eslint .`)                                       | PASS (0 errors, 57 warnings)                       |
| Frontend format                     | `pnpm format:check` (`prettier --check .`)                     | PASS                                               |
| Frontend types                      | `pnpm -r typecheck`                                            | PASS (3 packages)                                  |
| Frontend unit tests                 | `pnpm -r test`                                                 | PASS                                               |
| Production build                    | `pnpm --filter @ats/control-center build`                      | PASS                                               |
| Lockfile                            | `uv lock --check`                                              | PASS                                               |
| CI YAML                             | parsed and validated                                           | 10 jobs                                            |

The 8 + 61 skips are durability tests awaiting a Postgres DSN
(`ATS_TEST_POSTGRES_DSN` is unset locally); `tests/contract` and `tests/smoke`
are fully executed with no skips. They are gated in CI by the critical-suite
assertion below.

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

**Known follow-up, deliberately not closed here:** `engine.py:511` still sets
`authorized = isinstance(self.authority, NoopAuthorityService)`, which is always
true when the orchestrator constructs `TradingRuntime` without an authority, and
`NoopAuthorityService` answers `ALLOW`. The orchestrator's own provider now
gates independently, so this is defense-in-depth rather than an open escape
hatch, but it should be made explicit.

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

---

## Remaining Work

Ordered so that safety work lands before ergonomics. Each item names the file
evidence already gathered.

### P2 - Authorization escape hatches (DONE, except two recorded follow-ups)

Completed in `e853ea9` and documented under
[Phase 2](#phase-2---authorization-escape-hatches-committed-in-e853ea9):
exit-authorization seam with a fail-closed default, removal of
`_snapshot_position_id` / `_position_snapshot` / the literal `ALLOW`,
`seed_fill` moved out of the production adapter, placeholder identity minting in
`_build_order_intent` replaced by an explicit `OrderIntentBinding`, and
source-scanning guards plus seven-direction refusal tests.

Two items are **not** closed and should not be mistaken for being closed:

- **Entry authority is still an implicit permissive default in tests.**
  `tests/unit/trading_runtime/helpers.py` still has `authorization_provider or
allow_all`. Exit authority and entry _binding_ are both explicit; entry
  _authorization_ is not. Removing it means every entry test states its
  authority rather than inheriting it.
- **`engine.py:511`** still computes
  `authorized = isinstance(self.authority, NoopAuthorityService)`, which is
  always true when the orchestrator builds `TradingRuntime` without an
  authority, and `NoopAuthorityService` answers `ALLOW`. The orchestrator's own
  provider now gates independently, so this is defense-in-depth - but it is
  still a bypass that should be made explicit.

### P3/P5 - Frontend honesty

- `ShellWrapper.tsx:16` (`"use client"` placement) and `Shell.tsx:145-185` -
  ensure displayed state is not presented as authoritative when it is stale or
  unknown. Existing tests already assert UNKNOWN must not render as healthy;
  extend to every panel.
- `LiveChart.tsx` is 3,680 lines with 14 `any` warnings - split and type it.
- Verify every SSE-derived field degrades honestly on disconnect rather than
  freezing on last value.

### P4 - Agent management surface (§23)

- Build CRUD on the existing `backend/src/ats/agents/router.py` routes
  (roster CRUD at 176-250, config at 783-793), which today are largely stubs.
- Every mutating route must remain a _proposal_ or _advisory_ surface - no agent
  route may authorize execution. Enforce with a contract test mirroring
  `test_console_boundary.py`.

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
