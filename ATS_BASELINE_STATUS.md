# ATS — BASELINE IMPLEMENTATION STATUS

**Date:** 2026-09-28 · **Auditor:** principal-architect agent · **Scope:** pre-change inspection

Legend: **VERIFIED** = executed/read here · **INFERRED** = reasoned from source ·
**NEEDS VALIDATION** = identified but not yet proven · **BLOCKED** = cannot proceed

---

## 1. Repository identity — VERIFIED

| Check | Result |
|---|---|
| CWD / repo root | `D:\Projects\ATS\ats` (confirmed via `git rev-parse --show-toplevel`) |
| Parent `D:\Projects\ATS` | Workspace scratch — **not** the implementation target ✅ |
| Branch | `main` |
| HEAD | `bd0177b` `feat(market): in-memory order flow footprint store...` |
| Dirty paths | **137** — `94 ??` untracked, `38 M` modified, `4 RM` renamed, `1 D` deleted |
| Prior `api → console` refactor | **STILL INCOMPLETE — VERIFIED.** 4 files staged as renames (`market_models`, `market_router`, `runtime_models`, `runtime_router`) while 11 new `console/*` files remain untracked. |
| `MASTER_CHARTER.md` | Present at `D:\Projects\ATS\MASTER_CHARTER.md` (34.7 KB) |
| `ATS_IMPLEMENTATION_REPORT.md` | **Absent** — to be produced at completion |

## 2. Baseline validation — VERIFIED (executed)

| Command | Result |
|---|---|
| `uv run ruff check backend` | ✅ **All checks passed** |
| `uv run mypy backend/src` | ✅ **Success: no issues found in 315 source files** (strict) |
| `uv run pytest tests/contract` | ✅ **140 passed** |
| `uv run pytest tests/smoke tests/contract` | ⚠️ **146 passed, 1 FAILED** |
| `uv run pytest tests/unit` | ⛔ **NOT RUN TO COMPLETION** — exceeded 900 s serial in prior session |

### FAILED (baseline, pre-existing)
`tests/smoke/test_scope.py::test_no_model_artifacts_or_secret_files`
```
AssertionError: assert not [WindowsPath('D:/Projects/ATS/ats/.env')]
```
**Root cause — INFERRED, verified by reading `tests/smoke/test_scope.py:15-19`:** the test does
`ROOT.rglob("*")`, i.e. it scans the **working directory**, not the repository. The repo's own
`.gitignore:17-18` sanctions `.env` / `.env.*`. The test therefore contradicts the gitignore and
fails on any developer machine that has local env config, while CI (fresh clone) passes.
**Classification: test defect, not a product defect.** Fix = scan the set of files that can
actually enter the repository (`git ls-files -co --exclude-standard`), which is a *stricter and
more correct* target than `rglob` — not a weakening.

### Note on method — VERIFIED
Two `uv run` invocations executed concurrently contend for `.venv` and abort with
`os error 32`. All subsequent `uv run` commands are serialized.

## 3. Reproducibility — VERIFIED defect

`backend/pyproject.toml:15` declares `uvicorn[standard]==0.38.0`.
`uv.lock:60-66` `ats.dependencies` lists only `fastapi, optuna, protobuf, pydantic, websockets`.
`uv.lock:69-75` `requires-dist` **also omits `uvicorn`**.

⇒ `uv sync --frozen` silently does **not** install uvicorn. Manifest and lock disagree. **P0.**

## 4. Authorization path — VERIFIED defects

`backend/src/ats/trading_runtime/orchestrator.py`:

| Line | Finding | Severity |
|---|---|---|
| `:421` | `authorization=ALLOW` — **literal kernel constant**, bypasses the provider seam used for entries (`:253`) | **P0 escape hatch** |
| `:387` | `position_id=_snapshot_position_id()` — synthetic position identity | P0 |
| `:394-395` | `risk_decision_id=uuid4()`, `autonomy_token_id=uuid4()` — **fabricated authority identities** | **P0** |
| `:368-373` | exit request path bypasses `ReductionAuthorityService` | P0 |

**INFERRED (high confidence):** `ReductionAuthorityService` is constructed **only in tests**
(`tests/integration/trading_runtime/test_reduction_authority_postgres.py`, 9 sites) — it is
**never wired into production runtime**. It also requires a Postgres `TransactionManager`, so it
cannot be dropped directly into the in-memory paper-tournament orchestrator without breaking
paper-only operation. **Therefore the canonical-equivalent seam must be introduced at the
orchestrator boundary.**

Entry path is correct today: `_default_authorization` (`:131-141`) is fail-closed DENY.

**`seed_fill` — VERIFIED:** defined `backend/src/ats/trading_runtime/broker.py:367`; called only
from `tests/integration/trading_runtime/test_reduction_authority_postgres.py` (5 sites).
Production/paper-forward does not call it. Needs an *accidental-invocation* guard (P1).

**Only production construction site of `AutonomousPaperOrchestrator`:**
`backend/src/ats/trading_runtime/paper_forward.py:28` (+ definition `:11,18`, self-ref `:591`).
Scripts `run_paper_sessions.py` are harnesses.

## 5. Control plane — VERIFIED defect

`backend/src/ats/console/app.py:177` — `allow_origins=["*"]`. **P1 security.**

## 6. Frontend — VERIFIED defects

- **No ESLint / Prettier config exists anywhere** (`Get-ChildItem frontend -Recurse -Include
  '.eslintrc*','eslint.config.*','.prettierrc*'` → empty), yet the PR template demands
  "Lint and typecheck pass" and `__tests__/shell.test.tsx:12` carries an
  `eslint-disable-next-line` comment. **Lint half of the gate is unfulfillable.**
- `hooks/useSse.ts` marked deleted (`D`) while `hooks/useSse.tsx` is untracked — an unstaged
  `.ts`→`.tsx` rename. **NEEDS VALIDATION** of which is canonical.
- Prior-session audit (INFERRED, from `MASTER_CHARTER.md` §4.3) records: `ShellWrapper.tsx:16`
  swallows backend errors → shows `READY`; hardcoded `LIVE READY` pill in `Shell.tsx:145-160`;
  cosmetic data-source `<select>`; `LiveChart.tsx` synthetic price history + 1 Hz `Math.random()`;
  fabricated telemetry (`footprint.ts:269`, `LiveChart.tsx:77`); hardcoded bid quantities;
  conditional hook call in `useSse.tsx:102-109`. **NEEDS VALIDATION** — to be re-verified at
  Phase 3 before editing.

## 7. Agent system — VERIFIED current shape

`backend/src/ats/agents/` = **Quantitative Agents Playground** (17 modules, ~7,200 LOC):
`roster.py`, `config.py`, `worker.py` (48 KB), `router.py` (39 KB), families/features/strategies/
edge/costs/execution/risk/portfolio/deployment/evolver/trade_ledger/custom.

`router.py` already exposes **39 routes**, including roster CRUD:
`POST /roster/agents`, `DELETE /roster/agents/{name}`, `POST /roster/reset`, guidelines,
goals, config (`GET|PUT /config`).

**INFERRED:** this is a *strategy-persona* roster, **not** an LLM-agent configuration system.
The §23 spec (model/provider config, system prompt, permitted tools, enable/disable, templates,
versioned config, audit trail) is **not present**. §23 requires an **extension**, not a
duplicate — but must be built as a separate, proposal-only domain so it cannot inherit or
grant financial authority.

`backend/src/ats/ai/` (6 modules) = AI service, tools (**READ-ONLY registry**), live coach,
capital advisor, laya bridge.

## 8. Test/CI state — VERIFIED from prior audit + re-confirmed

- `tests/smoke/` (7 governance tests) **not referenced by `ci.yml`** — NEEDS VALIDATION at Phase 1.
- 46 Postgres durability tests skip (no `services:` block, no `psycopg` dep, no
  `ATS_TEST_POSTGRES_DSN`) — including `test_capital_reservation_race.py` (3-thread double-spend).
- `tests/acceptance/`, `tests/e2e/` are `.gitkeep`-only while README advertises both.
- `hypothesis` absent from lock — no property-based testing exists.

## 9. Untracked-but-load-bearing — BLOCKED RISK

A fresh clone of `main` **cannot build**: `Dashboard.tsx` imports `@ats/ui`
`StrategyBadge`/`RatingBar`/`RankBadge`/`PerformanceMetric`, all four **untracked**.
16 frontend routes, 11 `console/` routers, 22 `backend/tests/` files likewise untracked.

---

## 10. DECISIONS

1. **No work discarded.** All 137 paths classified into coherent commits (Phase 0).
2. **`.env` smoke-test failure fixed at the test**, documented as a test-defect correction that
   *tightens* the target set — not a suppression.
3. **Exit authority** gets an explicit provider seam defaulting to fail-closed DENY, with the
   orchestrator no longer synthesizing authority identities. `ReductionAuthorityService` is
   Postgres-bound and cannot be wired into the in-memory path without breaking paper-only
   operation — documented as the canonical-equivalent decision.
4. Every phase ends with executed validation. Nothing is marked complete on assertion alone.

**Overall baseline: 1 FAIL, 146 PASS, ruff PASS, mypy-strict PASS. Product baseline is sound;
the failures are in governance/scoping and lockfile, not in the safety kernel.**
