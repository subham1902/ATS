# XAUUSD / MT5 specialization inventory

Baseline: `5073e13983da86f99b31487587d449d4f06ed71c` on `main`. Actual product root: `D:/Projects/ATS/ats`.

This inventory was produced before deletion. The accompanying JSON records each path, classification, SHA-256, size and matched legacy terms. No serialized model was loaded. REVIEW entries require dependency inspection before deletion.

## Safety and authority

Keep the deterministic contracts/kernel, portfolio authority, durable token consumption and PaperBroker path. No real orders. Remove the startup synthetic tick and all outer-workspace evidence discovery. Existing managed-agent configuration is locally modified and must be recoverable. No performance claim transfers from another market.

## Scope decisions

- External provider: MT5, read-only. Canonical instrument: XAUUSD; broker symbol is configured separately.
- Upstox raw data, journals, replays, calibration and old strategy scores are deleted after recovery snapshot verification.
- Unattributed learned/derived state is PROVENANCE_UNKNOWN - NOT ELIGIBLE and cannot initialize the product.
- S5 becomes XAUUSD-native DESIGN / RESEARCH_ONLY with unresolved decisions retained.
- Managed research agents survive; the old capital-bearing persona playground is reviewed separately from the managed-agent boundary.
- Generic strategy definitions may survive; old fitness, promotion and tournament evidence does not.
- The outer workspace, toolchains and other Git worktrees are recovery/research material outside the active product. The specialized application must never read their old evidence.

## Classification counts

| Classification | Files |
| --- | ---: |
| DELETE | 227 |
| GENERATED/EPHEMERAL | 3 |
| KEEP GENERIC | 531 |
| REVIEW | 86 |
| REWRITE FOR XAUUSD | 165 |

## Per-file classification

| Path | Classification | Reason |
| --- | --- | --- |
| `.editorconfig` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `.env.example` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `.gitattributes` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `.github/CODEOWNERS` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `.github/dependabot.yml` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `.github/ISSUE_TEMPLATE/blank.md` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `.github/ISSUE_TEMPLATE/bug_report.md` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `.github/ISSUE_TEMPLATE/feature_request.md` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `.github/PULL_REQUEST_TEMPLATE.md` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `.github/workflows/ci.yml` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `.gitignore` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `.gitleaksignore` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `.npmrc` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `.nvmrc` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `.prettierignore` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `.prettierrc.json` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `.python-version` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `.tool-versions` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `ATS_BASELINE_STATUS.md` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `ATS_FEED_RESILIENCE_REPORT.md` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `ATS_HISTORY_LIVE_RECONCILIATION.md` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `ATS_IMPLEMENTATION_REPORT.md` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `ATS_LC1_BASELINE.md` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `ATS_LC1_FINAL_REPORT.md` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `ATS_LC1_MANIFEST.json` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `ATS_LC1_SECURITY_REPORT.md` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `ATS_LC1_TEST_REPORT.md` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `ATS_LIVE_CANDLE_ENGINE_SPEC.md` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `ATS_LIVE_CHART_ACCEPTANCE.md` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `ATS_LIVE_PROVIDER_ARCHITECTURE.md` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `ATS_MARKET_DATA_OBSERVABILITY.md` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `ATS_NORMALIZED_MARKET_EVENT_SPEC.md` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `ATS_STREAM_HUB_SPEC.md` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `ATS_UPSTOX_V3_STREAM_REPORT.md` | DELETE | Obsolete provider implementation, fixtures, tests or provider documentation. |
| `backend/migrations/.gitkeep` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/migrations/0001_iba_r17_evidence_store.sql` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/migrations/0002_portfolio_capital_reservations.sql` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/migrations/0003_position_reduction_authority_evidence.sql` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/migrations/README.md` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/pyproject.toml` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/__init__.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/agents/__init__.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/agents/config.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `backend/src/ats/agents/costs.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `backend/src/ats/agents/custom.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/agents/deployment.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/agents/edge.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/agents/evolver.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/agents/execution.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/agents/families.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/agents/features.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/agents/managed.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/agents/managed_router.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/agents/portfolio.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `backend/src/ats/agents/redaction.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/agents/risk.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/agents/roster.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `backend/src/ats/agents/router.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `backend/src/ats/agents/strategies.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/agents/trade_ledger.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `backend/src/ats/agents/worker.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `backend/src/ats/ai/__init__.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/ai/capital_advisor.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `backend/src/ats/ai/laya_bridge.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `backend/src/ats/ai/live_coach.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `backend/src/ats/ai/service.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `backend/src/ats/ai/tools.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/api/__init__.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/api/app.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/api/models.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/api/providers.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/api/stream.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/console/__init__.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/console/ai_router.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/console/app.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `backend/src/ats/console/broker_router.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `backend/src/ats/console/cors.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/console/datasets_router.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `backend/src/ats/console/governance_router.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `backend/src/ats/console/imported_strategies_router.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `backend/src/ats/console/laya_router.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `backend/src/ats/console/market_models.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `backend/src/ats/console/market_router.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `backend/src/ats/console/providers.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/console/runtime_models.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/console/runtime_router.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `backend/src/ats/console/settings_router.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `backend/src/ats/console/strategy_lab_router.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/console/strategy_registry.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/console/strategy_registry_models.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/console/strategy_registry_service.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `backend/src/ats/contracts/__init__.py` | KEEP GENERIC | Trusted authorization/settlement/durability boundary; change only market-specific seams if necessary. |
| `backend/src/ats/contracts/common/__init__.py` | KEEP GENERIC | Trusted authorization/settlement/durability boundary; change only market-specific seams if necessary. |
| `backend/src/ats/contracts/domain/__init__.py` | KEEP GENERIC | Trusted authorization/settlement/durability boundary; change only market-specific seams if necessary. |
| `backend/src/ats/contracts/domain/hashing.py` | KEEP GENERIC | Trusted authorization/settlement/durability boundary; change only market-specific seams if necessary. |
| `backend/src/ats/contracts/domain/models.py` | KEEP GENERIC | Trusted authorization/settlement/durability boundary; change only market-specific seams if necessary. |
| `backend/src/ats/contracts/domain/types.py` | KEEP GENERIC | Trusted authorization/settlement/durability boundary; change only market-specific seams if necessary. |
| `backend/src/ats/contracts/enums.py` | KEEP GENERIC | Trusted authorization/settlement/durability boundary; change only market-specific seams if necessary. |
| `backend/src/ats/contracts/events/__init__.py` | KEEP GENERIC | Trusted authorization/settlement/durability boundary; change only market-specific seams if necessary. |
| `backend/src/ats/contracts/events/models.py` | KEEP GENERIC | Trusted authorization/settlement/durability boundary; change only market-specific seams if necessary. |
| `backend/src/ats/contracts/events/registry.py` | KEEP GENERIC | Trusted authorization/settlement/durability boundary; change only market-specific seams if necessary. |
| `backend/src/ats/contracts/events/validation.py` | KEEP GENERIC | Trusted authorization/settlement/durability boundary; change only market-specific seams if necessary. |
| `backend/src/ats/contracts/governance/__init__.py` | KEEP GENERIC | Trusted authorization/settlement/durability boundary; change only market-specific seams if necessary. |
| `backend/src/ats/contracts/governance/models.py` | KEEP GENERIC | Trusted authorization/settlement/durability boundary; change only market-specific seams if necessary. |
| `backend/src/ats/contracts/governance/types.py` | KEEP GENERIC | Trusted authorization/settlement/durability boundary; change only market-specific seams if necessary. |
| `backend/src/ats/contracts/hashing.py` | KEEP GENERIC | Trusted authorization/settlement/durability boundary; change only market-specific seams if necessary. |
| `backend/src/ats/contracts/ids.py` | KEEP GENERIC | Trusted authorization/settlement/durability boundary; change only market-specific seams if necessary. |
| `backend/src/ats/contracts/intelligence/__init__.py` | KEEP GENERIC | Trusted authorization/settlement/durability boundary; change only market-specific seams if necessary. |
| `backend/src/ats/contracts/intelligence/models.py` | KEEP GENERIC | Trusted authorization/settlement/durability boundary; change only market-specific seams if necessary. |
| `backend/src/ats/contracts/intelligence/types.py` | KEEP GENERIC | Trusted authorization/settlement/durability boundary; change only market-specific seams if necessary. |
| `backend/src/ats/datasets/__init__.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/datasets/service.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `backend/src/ats/events/__init__.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/events/models.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/execution/__init__.py` | KEEP GENERIC | Trusted authorization/settlement/durability boundary; change only market-specific seams if necessary. |
| `backend/src/ats/execution/durability.py` | KEEP GENERIC | Trusted authorization/settlement/durability boundary; change only market-specific seams if necessary. |
| `backend/src/ats/execution/lifecycle/__init__.py` | KEEP GENERIC | Trusted authorization/settlement/durability boundary; change only market-specific seams if necessary. |
| `backend/src/ats/execution/lifecycle/journal.py` | KEEP GENERIC | Trusted authorization/settlement/durability boundary; change only market-specific seams if necessary. |
| `backend/src/ats/execution/lifecycle/machine.py` | KEEP GENERIC | Trusted authorization/settlement/durability boundary; change only market-specific seams if necessary. |
| `backend/src/ats/execution/lifecycle/models.py` | KEEP GENERIC | Trusted authorization/settlement/durability boundary; change only market-specific seams if necessary. |
| `backend/src/ats/execution/paper/__init__.py` | KEEP GENERIC | Trusted authorization/settlement/durability boundary; change only market-specific seams if necessary. |
| `backend/src/ats/execution/paper/broker.py` | KEEP GENERIC | Trusted authorization/settlement/durability boundary; change only market-specific seams if necessary. |
| `backend/src/ats/execution/paper/errors.py` | KEEP GENERIC | Trusted authorization/settlement/durability boundary; change only market-specific seams if necessary. |
| `backend/src/ats/execution/paper/models.py` | KEEP GENERIC | Trusted authorization/settlement/durability boundary; change only market-specific seams if necessary. |
| `backend/src/ats/forecast/__init__.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/forecast/models.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/forecast/naive.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/forecast/provider.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/forecast/worker.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/governance/campaign/__init__.py` | KEEP GENERIC | Trusted authorization/settlement/durability boundary; change only market-specific seams if necessary. |
| `backend/src/ats/governance/campaign/errors.py` | KEEP GENERIC | Trusted authorization/settlement/durability boundary; change only market-specific seams if necessary. |
| `backend/src/ats/governance/campaign/models.py` | KEEP GENERIC | Trusted authorization/settlement/durability boundary; change only market-specific seams if necessary. |
| `backend/src/ats/governance/campaign/runtime.py` | KEEP GENERIC | Trusted authorization/settlement/durability boundary; change only market-specific seams if necessary. |
| `backend/src/ats/governance/continuous/__init__.py` | KEEP GENERIC | Trusted authorization/settlement/durability boundary; change only market-specific seams if necessary. |
| `backend/src/ats/governance/continuous/models.py` | KEEP GENERIC | Trusted authorization/settlement/durability boundary; change only market-specific seams if necessary. |
| `backend/src/ats/governance/continuous/protocols.py` | KEEP GENERIC | Trusted authorization/settlement/durability boundary; change only market-specific seams if necessary. |
| `backend/src/ats/governance/continuous/runtime.py` | KEEP GENERIC | Trusted authorization/settlement/durability boundary; change only market-specific seams if necessary. |
| `backend/src/ats/governance/opportunity/__init__.py` | KEEP GENERIC | Trusted authorization/settlement/durability boundary; change only market-specific seams if necessary. |
| `backend/src/ats/governance/opportunity/errors.py` | KEEP GENERIC | Trusted authorization/settlement/durability boundary; change only market-specific seams if necessary. |
| `backend/src/ats/governance/opportunity/governor.py` | KEEP GENERIC | Trusted authorization/settlement/durability boundary; change only market-specific seams if necessary. |
| `backend/src/ats/governance/opportunity/models.py` | KEEP GENERIC | Trusted authorization/settlement/durability boundary; change only market-specific seams if necessary. |
| `backend/src/ats/governance/position/__init__.py` | KEEP GENERIC | Trusted authorization/settlement/durability boundary; change only market-specific seams if necessary. |
| `backend/src/ats/governance/position/governor.py` | KEEP GENERIC | Trusted authorization/settlement/durability boundary; change only market-specific seams if necessary. |
| `backend/src/ats/governance/position/models.py` | KEEP GENERIC | Trusted authorization/settlement/durability boundary; change only market-specific seams if necessary. |
| `backend/src/ats/intelligence/__init__.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/intelligence/advisory/__init__.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/intelligence/advisory/models.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/intelligence/advisory/protocols.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/intelligence/advisory/session.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/intelligence/calibration/__init__.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/intelligence/calibration/engine.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/intelligence/calibration/errors.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/intelligence/calibration/models.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/intelligence/ensemble/__init__.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/intelligence/ensemble/engine.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/intelligence/ensemble/errors.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/intelligence/ensemble/models.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/intelligence/formula/__init__.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/intelligence/formula/context.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/intelligence/formula/errors.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/intelligence/formula/evaluator.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/intelligence/formula/indicators.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/intelligence/formula/result.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/intelligence/harness/__init__.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/intelligence/harness/models.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/intelligence/harness/protocols.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/intelligence/harness/runtime.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/intelligence/harness/subprocess_sidecar.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/intelligence/inference/__init__.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/intelligence/inference/models.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/intelligence/inference/openrouter.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/intelligence/inference/transport.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/intelligence/instrument_selector/__init__.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/intelligence/instrument_selector/engine.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/intelligence/instrument_selector/errors.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/intelligence/instrument_selector/models.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/intelligence/llm/__init__.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/intelligence/regime/__init__.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/intelligence/regime/detector.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/intelligence/regime/errors.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/intelligence/regime/models.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/intelligence/strategy_lab/__init__.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/intelligence/strategy_lab/backtest.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/intelligence/strategy_lab/cost_model.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/intelligence/strategy_lab/dataset_binding.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/intelligence/strategy_lab/experiment_runner.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/intelligence/strategy_lab/fill_model.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/intelligence/strategy_lab/leakage_scanner.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/intelligence/strategy_lab/promotion_gate.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/intelligence/strategy_lab/scorecard.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/intelligence/strategy_lab/types.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/intelligence/strategy_lab/walk_forward.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/intelligence/thesis/__init__.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/intelligence/thesis/engine.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/intelligence/thesis/errors.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/intelligence/thesis/models.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/kernel/__init__.py` | KEEP GENERIC | Trusted authorization/settlement/durability boundary; change only market-specific seams if necessary. |
| `backend/src/ats/kernel/action_risk.py` | KEEP GENERIC | Trusted authorization/settlement/durability boundary; change only market-specific seams if necessary. |
| `backend/src/ats/kernel/autonomy.py` | KEEP GENERIC | Trusted authorization/settlement/durability boundary; change only market-specific seams if necessary. |
| `backend/src/ats/kernel/constraints.py` | KEEP GENERIC | Trusted authorization/settlement/durability boundary; change only market-specific seams if necessary. |
| `backend/src/ats/kernel/governance.py` | KEEP GENERIC | Trusted authorization/settlement/durability boundary; change only market-specific seams if necessary. |
| `backend/src/ats/kernel/loss_state.py` | KEEP GENERIC | Trusted authorization/settlement/durability boundary; change only market-specific seams if necessary. |
| `backend/src/ats/kernel/order_guard.py` | KEEP GENERIC | Trusted authorization/settlement/durability boundary; change only market-specific seams if necessary. |
| `backend/src/ats/kernel/policy.py` | KEEP GENERIC | Trusted authorization/settlement/durability boundary; change only market-specific seams if necessary. |
| `backend/src/ats/kernel/reduction.py` | KEEP GENERIC | Trusted authorization/settlement/durability boundary; change only market-specific seams if necessary. |
| `backend/src/ats/kernel/risk.py` | KEEP GENERIC | Trusted authorization/settlement/durability boundary; change only market-specific seams if necessary. |
| `backend/src/ats/kernel/types.py` | KEEP GENERIC | Trusted authorization/settlement/durability boundary; change only market-specific seams if necessary. |
| `backend/src/ats/kronos_worker/__init__.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/kronos_worker/adapter.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/market/__init__.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/market/calendar/__init__.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `backend/src/ats/market/calendar/models.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/market/data_acquisition/__init__.py` | DELETE | Obsolete provider implementation, fixtures, tests or provider documentation. |
| `backend/src/ats/market/data_acquisition/ingest_session.py` | DELETE | Obsolete provider implementation, fixtures, tests or provider documentation. |
| `backend/src/ats/market/data_acquisition/upstox_client.py` | DELETE | Obsolete provider implementation, fixtures, tests or provider documentation. |
| `backend/src/ats/market/derivatives/__init__.py` | REVIEW | Trace core references; remove acquisition/options logic and replace runtime instrument seam. |
| `backend/src/ats/market/derivatives/acquisition/__init__.py` | REVIEW | Trace core references; remove acquisition/options logic and replace runtime instrument seam. |
| `backend/src/ats/market/derivatives/acquisition/client.py` | REVIEW | Trace core references; remove acquisition/options logic and replace runtime instrument seam. |
| `backend/src/ats/market/derivatives/acquisition/models.py` | REVIEW | Trace core references; remove acquisition/options logic and replace runtime instrument seam. |
| `backend/src/ats/market/derivatives/acquisition/parsers.py` | REVIEW | Trace core references; remove acquisition/options logic and replace runtime instrument seam. |
| `backend/src/ats/market/derivatives/acquisition/plan.py` | REVIEW | Trace core references; remove acquisition/options logic and replace runtime instrument seam. |
| `backend/src/ats/market/derivatives/acquisition/redaction.py` | REVIEW | Trace core references; remove acquisition/options logic and replace runtime instrument seam. |
| `backend/src/ats/market/derivatives/acquisition/secrets.py` | REVIEW | Trace core references; remove acquisition/options logic and replace runtime instrument seam. |
| `backend/src/ats/market/derivatives/active_window/__init__.py` | REVIEW | Trace core references; remove acquisition/options logic and replace runtime instrument seam. |
| `backend/src/ats/market/derivatives/active_window/cache.py` | REVIEW | Trace core references; remove acquisition/options logic and replace runtime instrument seam. |
| `backend/src/ats/market/derivatives/active_window/engine.py` | REVIEW | Trace core references; remove acquisition/options logic and replace runtime instrument seam. |
| `backend/src/ats/market/derivatives/active_window/models.py` | REVIEW | Trace core references; remove acquisition/options logic and replace runtime instrument seam. |
| `backend/src/ats/market/derivatives/artifacts/__init__.py` | REVIEW | Trace core references; remove acquisition/options logic and replace runtime instrument seam. |
| `backend/src/ats/market/derivatives/artifacts/models.py` | REVIEW | Trace core references; remove acquisition/options logic and replace runtime instrument seam. |
| `backend/src/ats/market/derivatives/artifacts/provenance.py` | REVIEW | Trace core references; remove acquisition/options logic and replace runtime instrument seam. |
| `backend/src/ats/market/derivatives/artifacts/store.py` | REVIEW | Trace core references; remove acquisition/options logic and replace runtime instrument seam. |
| `backend/src/ats/market/derivatives/contract_master/__init__.py` | REVIEW | Trace core references; remove acquisition/options logic and replace runtime instrument seam. |
| `backend/src/ats/market/derivatives/contract_master/errors.py` | REVIEW | Trace core references; remove acquisition/options logic and replace runtime instrument seam. |
| `backend/src/ats/market/derivatives/contract_master/expiry.py` | REVIEW | Trace core references; remove acquisition/options logic and replace runtime instrument seam. |
| `backend/src/ats/market/derivatives/contract_master/models.py` | REVIEW | Trace core references; remove acquisition/options logic and replace runtime instrument seam. |
| `backend/src/ats/market/derivatives/contract_master/normalization.py` | REVIEW | Trace core references; remove acquisition/options logic and replace runtime instrument seam. |
| `backend/src/ats/market/derivatives/contract_master/registry.py` | REVIEW | Trace core references; remove acquisition/options logic and replace runtime instrument seam. |
| `backend/src/ats/market/derivatives/normalization/__init__.py` | REVIEW | Trace core references; remove acquisition/options logic and replace runtime instrument seam. |
| `backend/src/ats/market/derivatives/normalization/models.py` | REVIEW | Trace core references; remove acquisition/options logic and replace runtime instrument seam. |
| `backend/src/ats/market/derivatives/normalization/normalizer.py` | REVIEW | Trace core references; remove acquisition/options logic and replace runtime instrument seam. |
| `backend/src/ats/market/derivatives/option_chain/__init__.py` | REVIEW | Trace core references; remove acquisition/options logic and replace runtime instrument seam. |
| `backend/src/ats/market/derivatives/option_chain/builder.py` | REVIEW | Trace core references; remove acquisition/options logic and replace runtime instrument seam. |
| `backend/src/ats/market/derivatives/option_chain/errors.py` | REVIEW | Trace core references; remove acquisition/options logic and replace runtime instrument seam. |
| `backend/src/ats/market/derivatives/option_chain/features.py` | REVIEW | Trace core references; remove acquisition/options logic and replace runtime instrument seam. |
| `backend/src/ats/market/derivatives/option_chain/greeks_calculator.py` | REVIEW | Trace core references; remove acquisition/options logic and replace runtime instrument seam. |
| `backend/src/ats/market/derivatives/option_chain/models.py` | REVIEW | Trace core references; remove acquisition/options logic and replace runtime instrument seam. |
| `backend/src/ats/market/derivatives/providers/__init__.py` | REVIEW | Trace core references; remove acquisition/options logic and replace runtime instrument seam. |
| `backend/src/ats/market/derivatives/providers/models.py` | REVIEW | Trace core references; remove acquisition/options logic and replace runtime instrument seam. |
| `backend/src/ats/market/derivatives/providers/protocols.py` | REVIEW | Trace core references; remove acquisition/options logic and replace runtime instrument seam. |
| `backend/src/ats/market/derivatives/replay_data/__init__.py` | REVIEW | Trace core references; remove acquisition/options logic and replace runtime instrument seam. |
| `backend/src/ats/market/derivatives/replay_data/builder.py` | REVIEW | Trace core references; remove acquisition/options logic and replace runtime instrument seam. |
| `backend/src/ats/market/derivatives/replay_data/models.py` | REVIEW | Trace core references; remove acquisition/options logic and replace runtime instrument seam. |
| `backend/src/ats/market/derivatives/replay_data/resampler.py` | REVIEW | Trace core references; remove acquisition/options logic and replace runtime instrument seam. |
| `backend/src/ats/market/derivatives/strike_window/__init__.py` | REVIEW | Trace core references; remove acquisition/options logic and replace runtime instrument seam. |
| `backend/src/ats/market/derivatives/strike_window/engine.py` | REVIEW | Trace core references; remove acquisition/options logic and replace runtime instrument seam. |
| `backend/src/ats/market/derivatives/strike_window/errors.py` | REVIEW | Trace core references; remove acquisition/options logic and replace runtime instrument seam. |
| `backend/src/ats/market/derivatives/strike_window/models.py` | REVIEW | Trace core references; remove acquisition/options logic and replace runtime instrument seam. |
| `backend/src/ats/market/fabric.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `backend/src/ats/market/features/__init__.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/market/features/engine.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/market/features/errors.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/market/features/registry.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/market/feeds/__init__.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `backend/src/ats/market/feeds/upstox_v3/__init__.py` | DELETE | Obsolete provider implementation, fixtures, tests or provider documentation. |
| `backend/src/ats/market/feeds/upstox_v3/adapter.py` | DELETE | Obsolete provider implementation, fixtures, tests or provider documentation. |
| `backend/src/ats/market/feeds/upstox_v3/codec.py` | DELETE | Obsolete provider implementation, fixtures, tests or provider documentation. |
| `backend/src/ats/market/feeds/upstox_v3/config.py` | DELETE | Obsolete provider implementation, fixtures, tests or provider documentation. |
| `backend/src/ats/market/feeds/upstox_v3/errors.py` | DELETE | Obsolete provider implementation, fixtures, tests or provider documentation. |
| `backend/src/ats/market/feeds/upstox_v3/frames.py` | DELETE | Obsolete provider implementation, fixtures, tests or provider documentation. |
| `backend/src/ats/market/feeds/upstox_v3/freshness.py` | DELETE | Obsolete provider implementation, fixtures, tests or provider documentation. |
| `backend/src/ats/market/feeds/upstox_v3/instrument_keys.py` | DELETE | Obsolete provider implementation, fixtures, tests or provider documentation. |
| `backend/src/ats/market/feeds/upstox_v3/messages.py` | DELETE | Obsolete provider implementation, fixtures, tests or provider documentation. |
| `backend/src/ats/market/feeds/upstox_v3/proto/__init__.py` | DELETE | Obsolete provider implementation, fixtures, tests or provider documentation. |
| `backend/src/ats/market/feeds/upstox_v3/proto/MarketDataFeedV3.proto` | DELETE | Obsolete provider implementation, fixtures, tests or provider documentation. |
| `backend/src/ats/market/feeds/upstox_v3/proto/MarketDataFeedV3_pb2.py` | DELETE | Obsolete provider implementation, fixtures, tests or provider documentation. |
| `backend/src/ats/market/feeds/upstox_v3/proto/MarketDataFeedV3_pb2.pyi` | DELETE | Obsolete provider implementation, fixtures, tests or provider documentation. |
| `backend/src/ats/market/feeds/upstox_v3/proto/README.md` | DELETE | Obsolete provider implementation, fixtures, tests or provider documentation. |
| `backend/src/ats/market/feeds/upstox_v3/protobuf_codec.py` | DELETE | Obsolete provider implementation, fixtures, tests or provider documentation. |
| `backend/src/ats/market/feeds/upstox_v3/subscription.py` | DELETE | Obsolete provider implementation, fixtures, tests or provider documentation. |
| `backend/src/ats/market/feeds/upstox_v3/transport.py` | DELETE | Obsolete provider implementation, fixtures, tests or provider documentation. |
| `backend/src/ats/market/fixtures/__init__.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/market/fixtures/loader.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/market/fixtures/nse_cash_reliance_5m_v1.bars.json` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `backend/src/ats/market/fixtures/nse_cash_reliance_5m_v1.manifest.json` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `backend/src/ats/market/history/__init__.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/market/history/as_of.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/market/history/builder.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/market/history/dataset.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/market/history/errors.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/market/history/models.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/market/history/replay_bridge.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/market/history/storage.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/market/history/validation.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/market/intelligence_cache/__init__.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/market/intelligence_cache/cache.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/market/intelligence_cache/models.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/market/live/candle_builder.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `backend/src/ats/market/live/journal.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `backend/src/ats/market/live/state.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `backend/src/ats/market/live/stream_hub.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `backend/src/ats/market/live/subscriptions.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `backend/src/ats/market/live/upstox_v3.py` | DELETE | Obsolete provider implementation, fixtures, tests or provider documentation. |
| `backend/src/ats/market/providers/__init__.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/market/providers/base.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/market/providers/upstox/__init__.py` | DELETE | Obsolete provider implementation, fixtures, tests or provider documentation. |
| `backend/src/ats/market/providers/upstox/catalogue.py` | DELETE | Obsolete provider implementation, fixtures, tests or provider documentation. |
| `backend/src/ats/market/providers/upstox/models.py` | DELETE | Obsolete provider implementation, fixtures, tests or provider documentation. |
| `backend/src/ats/market/providers/upstox/protocols.py` | DELETE | Obsolete provider implementation, fixtures, tests or provider documentation. |
| `backend/src/ats/market/providers/upstox/rate_limit.py` | DELETE | Obsolete provider implementation, fixtures, tests or provider documentation. |
| `backend/src/ats/market/reference/__init__.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/market/reference/authority.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/market/replay/__init__.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/market/replay/engine.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/market/replay/models.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `backend/src/ats/market/strategy_import/__init__.py` | DELETE | Obsolete provider implementation, fixtures, tests or provider documentation. |
| `backend/src/ats/market/strategy_import/adapters.py` | DELETE | Obsolete provider implementation, fixtures, tests or provider documentation. |
| `backend/src/ats/market/strategy_import/decoder.py` | DELETE | Obsolete provider implementation, fixtures, tests or provider documentation. |
| `backend/src/ats/market/strategy_import/models.py` | DELETE | Obsolete provider implementation, fixtures, tests or provider documentation. |
| `backend/src/ats/market/strategy_import/tournament.py` | DELETE | Obsolete provider implementation, fixtures, tests or provider documentation. |
| `backend/src/ats/observability/__init__.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/observability/jev_telemetry.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/optimization/__init__.py` | DELETE | Obsolete provider implementation, fixtures, tests or provider documentation. |
| `backend/src/ats/optimization/router.py` | DELETE | Obsolete provider implementation, fixtures, tests or provider documentation. |
| `backend/src/ats/optimization/worker.py` | DELETE | Obsolete provider implementation, fixtures, tests or provider documentation. |
| `backend/src/ats/persistence/__init__.py` | KEEP GENERIC | Trusted authorization/settlement/durability boundary; change only market-specific seams if necessary. |
| `backend/src/ats/persistence/errors.py` | KEEP GENERIC | Trusted authorization/settlement/durability boundary; change only market-specific seams if necessary. |
| `backend/src/ats/persistence/json_files.py` | KEEP GENERIC | Trusted authorization/settlement/durability boundary; change only market-specific seams if necessary. |
| `backend/src/ats/persistence/migrations.py` | KEEP GENERIC | Trusted authorization/settlement/durability boundary; change only market-specific seams if necessary. |
| `backend/src/ats/persistence/postgres.py` | KEEP GENERIC | Trusted authorization/settlement/durability boundary; change only market-specific seams if necessary. |
| `backend/src/ats/persistence/protocols.py` | KEEP GENERIC | Trusted authorization/settlement/durability boundary; change only market-specific seams if necessary. |
| `backend/src/ats/persistence/types.py` | KEEP GENERIC | Trusted authorization/settlement/durability boundary; change only market-specific seams if necessary. |
| `backend/src/ats/portfolio/__init__.py` | KEEP GENERIC | Trusted authorization/settlement/durability boundary; change only market-specific seams if necessary. |
| `backend/src/ats/portfolio/persistence/__init__.py` | KEEP GENERIC | Trusted authorization/settlement/durability boundary; change only market-specific seams if necessary. |
| `backend/src/ats/portfolio/persistence/capital.py` | KEEP GENERIC | Trusted authorization/settlement/durability boundary; change only market-specific seams if necessary. |
| `backend/src/ats/portfolio/persistence/protocols.py` | KEEP GENERIC | Trusted authorization/settlement/durability boundary; change only market-specific seams if necessary. |
| `backend/src/ats/portfolio/runtime/__init__.py` | KEEP GENERIC | Trusted authorization/settlement/durability boundary; change only market-specific seams if necessary. |
| `backend/src/ats/portfolio/runtime/actor.py` | KEEP GENERIC | Trusted authorization/settlement/durability boundary; change only market-specific seams if necessary. |
| `backend/src/ats/portfolio/runtime/models.py` | KEEP GENERIC | Trusted authorization/settlement/durability boundary; change only market-specific seams if necessary. |
| `backend/src/ats/strategies/__init__.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/strategies/identity.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/strategies/lab_service.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `backend/src/ats/trading_runtime/__init__.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/trading_runtime/anti_churn.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/trading_runtime/authority.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/trading_runtime/authority_service.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/trading_runtime/broker.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/trading_runtime/candidate_factory.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/trading_runtime/engine.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `backend/src/ats/trading_runtime/exit_authority.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/trading_runtime/exit_authorization.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/trading_runtime/forward_validation.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/trading_runtime/hwm.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/trading_runtime/intelligence_pipeline.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/trading_runtime/lot_size.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `backend/src/ats/trading_runtime/modes.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/trading_runtime/orchestrator.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `backend/src/ats/trading_runtime/paper_forward.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `backend/src/ats/trading_runtime/paper_tournament.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `backend/src/ats/trading_runtime/position_authority.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/trading_runtime/position_monitor.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/trading_runtime/reconciliation.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/trading_runtime/reduction_authority.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/trading_runtime/runtime_provider.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/trading_runtime/safety.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/trading_runtime/session.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/ats/trading_runtime/startup.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `backend/src/ats/trading_runtime/strategy.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/src/data/market_journal/journal_upstox_20260924_07.jsonl` | DELETE | Legacy market state |
| `backend/src/data/market_journal/journal_upstox_20260924_08.jsonl` | DELETE | Legacy market state |
| `backend/tests/test_agents_cost_gate.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `backend/tests/test_agents_deployment_gate.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/tests/test_agents_edge_portfolio_execution.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `backend/tests/test_agents_features.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/tests/test_agents_market_resolution.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `backend/tests/test_agents_playground.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `backend/tests/test_agents_risk.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/tests/test_agents_risk_api.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `backend/tests/test_agents_roster_custom.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/tests/test_agents_strategies.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/tests/test_agents_worker_e2e.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `backend/tests/test_ai_service.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `backend/tests/test_console_cors.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/tests/test_datasets_registry.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `backend/tests/test_governance_router.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `backend/tests/test_jev_shadow.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/tests/test_json_store_integrity.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `backend/tests/test_live_streaming_engine.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `backend/tests/test_managed_agents.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/tests/test_market_fabric.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `backend/tests/test_paper_control_center.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `backend/tests/test_paper_tournament.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `backend/tests/test_port_3000_guard.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/tests/test_sse_stream.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `backend/tests/test_strategy_identity.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `backend/tests/test_strategy_import.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `benchmarks/bm_01/.gitkeep` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `benchmarks/bm_02/.gitkeep` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `benchmarks/bm_04/.gitkeep` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `benchmarks/bm_06/.gitkeep` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `benchmarks/strategy_lab/bench.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `data/agents/agents_config.json` | DELETE | Legacy market state |
| `data/agents/roster.json` | DELETE | Legacy market state |
| `data/agents/upstox_live_trades_ledger.json` | DELETE | Legacy market state |
| `data/datasets/datasets_manifest.json` | DELETE | PROVENANCE_UNKNOWN - NOT ELIGIBLE; reset learned/performance/runtime state. |
| `data/duckdb/.gitkeep` | KEEP GENERIC | Empty storage boundary; no market evidence. |
| `data/fixtures/.gitkeep` | KEEP GENERIC | Empty storage boundary; no market evidence. |
| `data/forward_validation/evidence_ledger.jsonl` | DELETE | PROVENANCE_UNKNOWN - NOT ELIGIBLE; reset learned/performance/runtime state. |
| `data/historical/banknifty_options_a2_replay_v1/manifest.json` | DELETE | Legacy market state |
| `data/historical/banknifty_options_a2_replay_v1/observations.jsonl` | DELETE | Legacy market state |
| `data/historical/banknifty_options_a2_replay_v1/policy.json` | DELETE | Legacy market state |
| `data/historical/banknifty_options_a2_replay_v1/records.sha256` | DELETE | Legacy market state |
| `data/historical/calibration_store_v1.json` | DELETE | PROVENANCE_UNKNOWN - NOT ELIGIBLE; reset learned/performance/runtime state. |
| `data/historical/calibration_stores/A1_calibration_store.json` | DELETE | PROVENANCE_UNKNOWN - NOT ELIGIBLE; reset learned/performance/runtime state. |
| `data/historical/calibration_stores/A2_calibration_store.json` | DELETE | PROVENANCE_UNKNOWN - NOT ELIGIBLE; reset learned/performance/runtime state. |
| `data/historical/calibration_stores/A3_calibration_store.json` | DELETE | PROVENANCE_UNKNOWN - NOT ELIGIBLE; reset learned/performance/runtime state. |
| `data/historical/calibration_stores/A4_calibration_store.json` | DELETE | PROVENANCE_UNKNOWN - NOT ELIGIBLE; reset learned/performance/runtime state. |
| `data/historical/calibration_stores/C0_calibration_store.json` | DELETE | PROVENANCE_UNKNOWN - NOT ELIGIBLE; reset learned/performance/runtime state. |
| `data/historical/calibration_stores/C1_calibration_store.json` | DELETE | PROVENANCE_UNKNOWN - NOT ELIGIBLE; reset learned/performance/runtime state. |
| `data/historical/calibration_stores/C2_calibration_store.json` | DELETE | PROVENANCE_UNKNOWN - NOT ELIGIBLE; reset learned/performance/runtime state. |
| `data/historical/calibration_stores/C3_calibration_store.json` | DELETE | PROVENANCE_UNKNOWN - NOT ELIGIBLE; reset learned/performance/runtime state. |
| `data/historical/calibration_stores/C4_calibration_store.json` | DELETE | PROVENANCE_UNKNOWN - NOT ELIGIBLE; reset learned/performance/runtime state. |
| `data/historical/calibration_stores/C5_calibration_store.json` | DELETE | PROVENANCE_UNKNOWN - NOT ELIGIBLE; reset learned/performance/runtime state. |
| `data/historical/nifty_options_a2_replay_v1/manifest.json` | DELETE | Legacy market state |
| `data/historical/nifty_options_a2_replay_v1/observations.jsonl` | DELETE | Legacy market state |
| `data/historical/nifty_options_a2_replay_v1/policy.json` | DELETE | Legacy market state |
| `data/historical/nifty_options_a2_replay_v1/records.sha256` | DELETE | Legacy market state |
| `data/market_journal/journal_upstox_20260923_18.jsonl` | DELETE | Legacy market state |
| `data/market_journal/journal_upstox_20260924_04.jsonl` | DELETE | Legacy market state |
| `data/market_journal/journal_upstox_20260924_05.jsonl` | DELETE | Legacy market state |
| `data/market_journal/journal_upstox_20260924_06.jsonl` | DELETE | Legacy market state |
| `data/market_journal/journal_upstox_20260924_07.jsonl` | DELETE | Legacy market state |
| `data/market_journal/journal_upstox_20260924_08.jsonl` | DELETE | Legacy market state |
| `data/market_journal/journal_upstox_20260924_16.jsonl` | DELETE | Legacy market state |
| `data/market_journal/journal_upstox_20260924_17.jsonl` | DELETE | Legacy market state |
| `data/market_journal/journal_upstox_20260924_18.jsonl` | DELETE | Legacy market state |
| `data/market_journal/journal_upstox_20260924_19.jsonl` | DELETE | Legacy market state |
| `data/market_journal/journal_upstox_20260924_20.jsonl` | DELETE | Legacy market state |
| `data/market_journal/journal_upstox_20260924_21.jsonl` | DELETE | Legacy market state |
| `data/market_journal/journal_upstox_20260924_22.jsonl` | DELETE | Legacy market state |
| `data/market_journal/journal_upstox_20260924_23.jsonl` | DELETE | Legacy market state |
| `data/market_journal/journal_upstox_20260925_03.jsonl` | DELETE | Legacy market state |
| `data/market_journal/journal_upstox_20260925_04.jsonl` | DELETE | Legacy market state |
| `data/market_journal/journal_upstox_20260925_05.jsonl` | DELETE | Legacy market state |
| `data/market_journal/journal_upstox_20260925_06.jsonl` | DELETE | Legacy market state |
| `data/market_journal/journal_upstox_20260925_07.jsonl` | DELETE | Legacy market state |
| `data/market_journal/journal_upstox_20260925_08.jsonl` | DELETE | Legacy market state |
| `data/market_journal/journal_upstox_20260925_09.jsonl` | DELETE | Legacy market state |
| `data/market_journal/journal_upstox_20260925_10.jsonl` | DELETE | Legacy market state |
| `data/market_journal/journal_upstox_20260925_11.jsonl` | DELETE | Legacy market state |
| `data/market_journal/journal_upstox_20260925_12.jsonl` | DELETE | Legacy market state |
| `data/market_journal/journal_upstox_20260925_13.jsonl` | DELETE | Legacy market state |
| `data/market_journal/journal_upstox_20260925_14.jsonl` | DELETE | Legacy market state |
| `data/market_journal/journal_upstox_20260925_15.jsonl` | DELETE | Legacy market state |
| `data/market_journal/journal_upstox_20260925_16.jsonl` | DELETE | Legacy market state |
| `data/market_journal/journal_upstox_20260925_17.jsonl` | DELETE | Legacy market state |
| `data/market_journal/journal_upstox_20260925_22.jsonl` | DELETE | Legacy market state |
| `data/market_journal/journal_upstox_20260926_06.jsonl` | DELETE | Legacy market state |
| `data/market_journal/journal_upstox_20260926_16.jsonl` | DELETE | Legacy market state |
| `data/market_journal/journal_upstox_20260927_02.jsonl` | DELETE | Legacy market state |
| `data/market_journal/journal_upstox_20260927_09.jsonl` | DELETE | Legacy market state |
| `data/market_journal/journal_upstox_20260927_10.jsonl` | DELETE | Legacy market state |
| `data/market_journal/journal_upstox_20260927_14.jsonl` | DELETE | Legacy market state |
| `data/market_journal/journal_upstox_20260927_16.jsonl` | DELETE | Legacy market state |
| `data/market_journal/journal_upstox_20260927_17.jsonl` | DELETE | Legacy market state |
| `data/market_journal/journal_upstox_20260927_18.jsonl` | DELETE | Legacy market state |
| `data/market_journal/journal_upstox_20260927_19.jsonl` | DELETE | Legacy market state |
| `data/market_journal/journal_upstox_20260928_08.jsonl` | DELETE | Legacy market state |
| `data/market_journal/journal_upstox_20260928_09.jsonl` | DELETE | Legacy market state |
| `data/market_journal/journal_upstox_20260928_10.jsonl` | DELETE | Legacy market state |
| `data/market_journal/journal_upstox_20260928_11.jsonl` | DELETE | Legacy market state |
| `data/market_journal/journal_upstox_20260928_12.jsonl` | DELETE | Legacy market state |
| `data/market_journal/journal_upstox_20260928_13.jsonl` | DELETE | Legacy market state |
| `data/market_journal/journal_upstox_20260928_14.jsonl` | DELETE | Legacy market state |
| `data/market_journal/journal_upstox_20260928_15.jsonl` | DELETE | Legacy market state |
| `data/market_journal/journal_upstox_20260928_16.jsonl` | DELETE | Legacy market state |
| `data/market_journal/journal_upstox_20260928_17.jsonl` | DELETE | Legacy market state |
| `data/market_journal/journal_upstox_20260929_08.jsonl` | DELETE | Legacy market state |
| `data/market_journal/journal_upstox_20260929_09.jsonl` | DELETE | Legacy market state |
| `data/market_journal/journal_upstox_20260929_10.jsonl` | DELETE | Legacy market state |
| `data/market_journal/journal_upstox_20260930_05.jsonl` | DELETE | Legacy market state |
| `data/market_journal/journal_upstox_20260930_06.jsonl` | DELETE | Legacy market state |
| `data/market_journal/journal_upstox_20260930_07.jsonl` | DELETE | Legacy market state |
| `data/market_journal/journal_upstox_20261001_04.jsonl` | DELETE | Legacy market state |
| `data/market_journal/journal_upstox_20261001_05.jsonl` | DELETE | Legacy market state |
| `data/market_journal/journal_upstox_20261001_06.jsonl` | DELETE | Legacy market state |
| `data/market_journal/journal_upstox_20261001_07.jsonl` | DELETE | Legacy market state |
| `data/market_journal/journal_upstox_20261001_08.jsonl` | DELETE | Legacy market state |
| `data/market_journal/journal_upstox_20261001_09.jsonl` | DELETE | Legacy market state |
| `data/market_journal/journal_upstox_20261001_10.jsonl` | DELETE | Legacy market state |
| `data/market_journal/journal_upstox_20261003_10.jsonl` | DELETE | Legacy market state |
| `data/market_journal/journal_upstox_20261003_11.jsonl` | DELETE | Legacy market state |
| `data/market_journal/journal_upstox_20261004_11.jsonl` | DELETE | Legacy market state |
| `data/market_journal/journal_upstox_20261005_12.jsonl` | DELETE | Legacy market state |
| `data/market_journal/journal_upstox_20261005_13.jsonl` | DELETE | Legacy market state |
| `data/market_journal/journal_upstox_20261005_21.jsonl` | DELETE | Legacy market state |
| `data/market_journal/journal_upstox_20261006_10.jsonl` | DELETE | Legacy market state |
| `data/parquet/.gitkeep` | KEEP GENERIC | Empty storage boundary; no market evidence. |
| `data/raw/upstox/banknifty_option_chain.json` | DELETE | Legacy market state |
| `data/raw/upstox/nifty_option_chain.json` | DELETE | Legacy market state |
| `data/raw/upstox/sessions/2026-08-04/BANKNIFTY_underlying.json` | DELETE | Legacy market state |
| `data/raw/upstox/sessions/2026-08-04/NIFTY_underlying.json` | DELETE | Legacy market state |
| `data/raw/upstox/sessions/2026-08-05/BANKNIFTY_underlying.json` | DELETE | Legacy market state |
| `data/raw/upstox/sessions/2026-08-05/NIFTY_underlying.json` | DELETE | Legacy market state |
| `data/raw/upstox/sessions/2026-08-06/BANKNIFTY_underlying.json` | DELETE | Legacy market state |
| `data/raw/upstox/sessions/2026-08-06/NIFTY_underlying.json` | DELETE | Legacy market state |
| `data/raw/upstox/sessions/2026-08-07/BANKNIFTY_underlying.json` | DELETE | Legacy market state |
| `data/raw/upstox/sessions/2026-08-07/NIFTY_underlying.json` | DELETE | Legacy market state |
| `data/raw/upstox/sessions/2026-08-10/BANKNIFTY_underlying.json` | DELETE | Legacy market state |
| `data/raw/upstox/sessions/2026-08-10/NIFTY_underlying.json` | DELETE | Legacy market state |
| `data/raw/upstox/sessions/2026-08-11/BANKNIFTY_underlying.json` | DELETE | Legacy market state |
| `data/raw/upstox/sessions/2026-08-11/NIFTY_underlying.json` | DELETE | Legacy market state |
| `data/raw/upstox/sessions/2026-08-12/BANKNIFTY_underlying.json` | DELETE | Legacy market state |
| `data/raw/upstox/sessions/2026-08-12/NIFTY_underlying.json` | DELETE | Legacy market state |
| `data/raw/upstox/sessions/2026-08-13/BANKNIFTY_underlying.json` | DELETE | Legacy market state |
| `data/raw/upstox/sessions/2026-08-13/NIFTY_underlying.json` | DELETE | Legacy market state |
| `data/raw/upstox/sessions/2026-08-14/BANKNIFTY_underlying.json` | DELETE | Legacy market state |
| `data/raw/upstox/sessions/2026-08-14/NIFTY_underlying.json` | DELETE | Legacy market state |
| `data/raw/upstox/sessions/2026-08-17/BANKNIFTY_underlying.json` | DELETE | Legacy market state |
| `data/raw/upstox/sessions/2026-08-17/NIFTY_underlying.json` | DELETE | Legacy market state |
| `data/raw/upstox/sessions/2026-08-18/BANKNIFTY_underlying.json` | DELETE | Legacy market state |
| `data/raw/upstox/sessions/2026-08-18/NIFTY_underlying.json` | DELETE | Legacy market state |
| `data/raw/upstox/sessions/2026-08-19/BANKNIFTY_underlying.json` | DELETE | Legacy market state |
| `data/raw/upstox/sessions/2026-08-19/NIFTY_underlying.json` | DELETE | Legacy market state |
| `data/raw/upstox/sessions/2026-08-20/BANKNIFTY_underlying.json` | DELETE | Legacy market state |
| `data/raw/upstox/sessions/2026-08-20/NIFTY_underlying.json` | DELETE | Legacy market state |
| `data/raw/upstox/sessions/2026-08-21/BANKNIFTY_underlying.json` | DELETE | Legacy market state |
| `data/raw/upstox/sessions/2026-08-21/NIFTY_underlying.json` | DELETE | Legacy market state |
| `data/raw/upstox/sessions/2026-08-24/BANKNIFTY_underlying.json` | DELETE | Legacy market state |
| `data/raw/upstox/sessions/2026-08-24/NIFTY_underlying.json` | DELETE | Legacy market state |
| `data/raw/upstox/sessions/2026-08-25/BANKNIFTY_opt_NSE_FO_69824.json` | DELETE | Legacy market state |
| `data/raw/upstox/sessions/2026-08-25/BANKNIFTY_opt_NSE_FO_69825.json` | DELETE | Legacy market state |
| `data/raw/upstox/sessions/2026-08-25/BANKNIFTY_opt_NSE_FO_69826.json` | DELETE | Legacy market state |
| `data/raw/upstox/sessions/2026-08-25/BANKNIFTY_opt_NSE_FO_69827.json` | DELETE | Legacy market state |
| `data/raw/upstox/sessions/2026-08-25/BANKNIFTY_opt_NSE_FO_69828.json` | DELETE | Legacy market state |
| `data/raw/upstox/sessions/2026-08-25/BANKNIFTY_opt_NSE_FO_69829.json` | DELETE | Legacy market state |
| `data/raw/upstox/sessions/2026-08-25/BANKNIFTY_opt_NSE_FO_69832.json` | DELETE | Legacy market state |
| `data/raw/upstox/sessions/2026-08-25/BANKNIFTY_opt_NSE_FO_69833.json` | DELETE | Legacy market state |
| `data/raw/upstox/sessions/2026-08-25/BANKNIFTY_opt_NSE_FO_69838.json` | DELETE | Legacy market state |
| `data/raw/upstox/sessions/2026-08-25/BANKNIFTY_opt_NSE_FO_69839.json` | DELETE | Legacy market state |
| `data/raw/upstox/sessions/2026-08-25/BANKNIFTY_underlying.json` | DELETE | Legacy market state |
| `data/raw/upstox/sessions/2026-08-25/NIFTY_opt_NSE_FO_46989.json` | DELETE | Legacy market state |
| `data/raw/upstox/sessions/2026-08-25/NIFTY_opt_NSE_FO_46990.json` | DELETE | Legacy market state |
| `data/raw/upstox/sessions/2026-08-25/NIFTY_opt_NSE_FO_46991.json` | DELETE | Legacy market state |
| `data/raw/upstox/sessions/2026-08-25/NIFTY_opt_NSE_FO_46992.json` | DELETE | Legacy market state |
| `data/raw/upstox/sessions/2026-08-25/NIFTY_opt_NSE_FO_46993.json` | DELETE | Legacy market state |
| `data/raw/upstox/sessions/2026-08-25/NIFTY_opt_NSE_FO_46994.json` | DELETE | Legacy market state |
| `data/raw/upstox/sessions/2026-08-25/NIFTY_opt_NSE_FO_46995.json` | DELETE | Legacy market state |
| `data/raw/upstox/sessions/2026-08-25/NIFTY_opt_NSE_FO_46996.json` | DELETE | Legacy market state |
| `data/raw/upstox/sessions/2026-08-25/NIFTY_opt_NSE_FO_46997.json` | DELETE | Legacy market state |
| `data/raw/upstox/sessions/2026-08-25/NIFTY_opt_NSE_FO_46998.json` | DELETE | Legacy market state |
| `data/raw/upstox/sessions/2026-08-25/NIFTY_underlying.json` | DELETE | Legacy market state |
| `data/raw/upstox/sessions/2026-08-25/session_manifest.json` | DELETE | Legacy market state |
| `data/raw/upstox/sessions/2026-08-26/BANKNIFTY_underlying.json` | DELETE | Legacy market state |
| `data/raw/upstox/sessions/2026-08-26/NIFTY_underlying.json` | DELETE | Legacy market state |
| `data/raw/upstox/sessions/2026-08-27/BANKNIFTY_underlying.json` | DELETE | Legacy market state |
| `data/raw/upstox/sessions/2026-08-27/NIFTY_underlying.json` | DELETE | Legacy market state |
| `data/raw/upstox/sessions/2026-08-28/BANKNIFTY_underlying.json` | DELETE | Legacy market state |
| `data/raw/upstox/sessions/2026-08-28/NIFTY_underlying.json` | DELETE | Legacy market state |
| `data/raw/upstox/upstox_bod_instruments_master.csv` | DELETE | Legacy market state |
| `data/replays/challenger_tournament_v1/tournament_summary.json` | DELETE | PROVENANCE_UNKNOWN - NOT ELIGIBLE; reset learned/performance/runtime state. |
| `data/replays/champion_replacement_tournament_v2/tournament_scorecard_v2.json` | DELETE | PROVENANCE_UNKNOWN - NOT ELIGIBLE; reset learned/performance/runtime state. |
| `data/replays/micro_edge_discovery_v2/micro_edge_discovery_summary.json` | DELETE | PROVENANCE_UNKNOWN - NOT ELIGIBLE; reset learned/performance/runtime state. |
| `data/replays/walk_forward_2026-08-04_to_2026-08-25/walk_forward_summary.json` | DELETE | PROVENANCE_UNKNOWN - NOT ELIGIBLE; reset learned/performance/runtime state. |
| `data/runtime/pre_market_acceptance.json` | DELETE | Legacy market state |
| `dist/.gitignore` | GENERATED/EPHEMERAL | Rebuild from specialized source. |
| `dist/ats-0.0.0-py3-none-any.whl` | GENERATED/EPHEMERAL | Rebuild from specialized source. |
| `dist/ats-0.0.0.tar.gz` | GENERATED/EPHEMERAL | Rebuild from specialized source. |
| `docs/adrs/.gitkeep` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `docs/architecture/.gitkeep` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `docs/evidence/.gitkeep` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `docs/JEV_INTEGRATION.md` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `docs/research/MCX_GOLD_STRATEGY_READINESS_AUDIT.md` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `docs/superpowers/specs/2026-09-30-s5-orb-mcx-gold-design.md` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `docs/superpowers/specs/2026-10-01-s5-open-decisions.md` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `docs/third-party/deepseek-harness.md` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `eslint.config.mjs` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `FORWARD_TEST_READINESS_REPORT.md` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `frontend/apps/control-center/__tests__/jev_api.test.ts` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `frontend/apps/control-center/__tests__/managed_agents.test.tsx` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `frontend/apps/control-center/__tests__/shell.test.tsx` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `frontend/apps/control-center/app/activity/page.tsx` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `frontend/apps/control-center/app/advisories/page.tsx` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `frontend/apps/control-center/app/agents/managed/[id]/page.tsx` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `frontend/apps/control-center/app/agents/managed/page.tsx` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `frontend/apps/control-center/app/agents/page.tsx` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `frontend/apps/control-center/app/api/jev/health/route.ts` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `frontend/apps/control-center/app/api/jev/route.ts` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `frontend/apps/control-center/app/broker/page.tsx` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `frontend/apps/control-center/app/candidates/page.tsx` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `frontend/apps/control-center/app/datasets/page.tsx` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `frontend/apps/control-center/app/governance/page.tsx` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `frontend/apps/control-center/app/health/page.tsx` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `frontend/apps/control-center/app/layout.tsx` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `frontend/apps/control-center/app/ledger/page.tsx` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `frontend/apps/control-center/app/market/page.tsx` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `frontend/apps/control-center/app/optimizations/page.tsx` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `frontend/apps/control-center/app/page.tsx` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `frontend/apps/control-center/app/paper/page.tsx` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `frontend/apps/control-center/app/policies/page.tsx` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `frontend/apps/control-center/app/research/capital-showdown/page.tsx` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `frontend/apps/control-center/app/research/page.tsx` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `frontend/apps/control-center/app/risk/page.tsx` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `frontend/apps/control-center/app/settings/page.tsx` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `frontend/apps/control-center/app/shadow/page.tsx` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `frontend/apps/control-center/app/ShellWrapper.tsx` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `frontend/apps/control-center/app/strategies/[id]/page.tsx` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `frontend/apps/control-center/app/strategies/imported/page.tsx` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `frontend/apps/control-center/app/strategies/page.tsx` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `frontend/apps/control-center/app/strategies/StrategyLabView.tsx` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `frontend/apps/control-center/app/survivors/page.tsx` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `frontend/apps/control-center/app/terminal/page.tsx` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `frontend/apps/control-center/app/tokens/page.tsx` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `frontend/apps/control-center/app/upstox-ledger/page.tsx` | DELETE | Obsolete provider implementation, fixtures, tests or provider documentation. |
| `frontend/apps/control-center/components/AICopilotPanel.tsx` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `frontend/apps/control-center/components/Dashboard.tsx` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `frontend/apps/control-center/components/LiveChart.tsx` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `frontend/apps/control-center/components/Lookup.tsx` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `frontend/apps/control-center/components/managed/ManagedAgentDetail.tsx` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `frontend/apps/control-center/components/managed/ManagedAgentsView.tsx` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `frontend/apps/control-center/components/managed/ManagedAgentWizard.tsx` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `frontend/apps/control-center/components/managed/shared.tsx` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `frontend/apps/control-center/components/panels.tsx` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `frontend/apps/control-center/components/Shell.tsx` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `frontend/apps/control-center/hooks/useMarketFeed.ts` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `frontend/apps/control-center/hooks/useSse.tsx` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `frontend/apps/control-center/lib/__tests__/dataSource.test.tsx` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `frontend/apps/control-center/lib/__tests__/provenance.test.ts` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `frontend/apps/control-center/lib/api.ts` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `frontend/apps/control-center/lib/dataSource.tsx` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `frontend/apps/control-center/lib/footprint.ts` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `frontend/apps/control-center/lib/marketHours.ts` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `frontend/apps/control-center/lib/provenance.ts` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `frontend/apps/control-center/next-env.d.ts` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `frontend/apps/control-center/next.config.mjs` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `frontend/apps/control-center/package.json` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `frontend/apps/control-center/tsconfig.json` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `frontend/apps/control-center/vitest.config.ts` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `frontend/apps/control-center/vitest.setup.ts` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `frontend/packages/api-client/package.json` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `frontend/packages/api-client/src/__tests__/contract.test.ts` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `frontend/packages/api-client/src/__tests__/managed_agents.test.ts` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `frontend/packages/api-client/src/client.ts` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `frontend/packages/api-client/src/index.ts` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `frontend/packages/api-client/src/sse.ts` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `frontend/packages/api-client/src/types.ts` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `frontend/packages/api-client/tsconfig.json` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `frontend/packages/api-client/vitest.config.ts` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `frontend/packages/ui/package.json` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `frontend/packages/ui/src/__tests__/ui.test.tsx` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `frontend/packages/ui/src/components/Badge.tsx` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `frontend/packages/ui/src/components/Card.tsx` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `frontend/packages/ui/src/components/ConnectionIndicator.tsx` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `frontend/packages/ui/src/components/DetailField.tsx` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `frontend/packages/ui/src/components/EmptyState.tsx` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `frontend/packages/ui/src/components/ErrorEnvelopeView.tsx` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `frontend/packages/ui/src/components/PerformanceMetric.tsx` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `frontend/packages/ui/src/components/RankBadge.tsx` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `frontend/packages/ui/src/components/RatingBar.tsx` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `frontend/packages/ui/src/components/StrategyBadge.tsx` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `frontend/packages/ui/src/components/SystemStateBadge.tsx` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `frontend/packages/ui/src/index.ts` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `frontend/packages/ui/tsconfig.json` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `frontend/packages/ui/vitest.config.ts` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `frontend/packages/ui/vitest.setup.ts` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `ownership.json` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `package.json` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `pnpm-lock.yaml` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `pnpm-workspace.yaml` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `pyproject.toml` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `README.md` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `reports/ATS_BROKER_CAPABILITY_MATRIX.csv` | DELETE | Legacy market state |
| `reports/ATS_BROKER_CONNECTION_GUIDE.md` | DELETE | Legacy market state |
| `reports/ATS_BROKER_CONNECTOR_ARCHITECTURE.md` | DELETE | Legacy market state |
| `reports/ATS_BROKER_SECURITY_REPORT.md` | DELETE | PROVENANCE_UNKNOWN - NOT ELIGIBLE; reset learned/performance/runtime state. |
| `reports/ATS_LIVE_MARKET_PAPER_REPORT.md` | DELETE | Legacy market state |
| `reports/ATS_LIVE_PAPER_BROWSER_ACCEPTANCE.md` | DELETE | PROVENANCE_UNKNOWN - NOT ELIGIBLE; reset learned/performance/runtime state. |
| `reports/ATS_LIVE_PAPER_WIRING_MAP.md` | DELETE | PROVENANCE_UNKNOWN - NOT ELIGIBLE; reset learned/performance/runtime state. |
| `reports/ATS_PLATFORM_FULL_REGRESSION_REPORT.md` | DELETE | PROVENANCE_UNKNOWN - NOT ELIGIBLE; reset learned/performance/runtime state. |
| `reports/ATS_PRODUCT_READINESS_MANIFEST.json` | DELETE | Legacy market state |
| `reports/ATS_SETTINGS_CONTROL_PLANE_REPORT.md` | DELETE | PROVENANCE_UNKNOWN - NOT ELIGIBLE; reset learned/performance/runtime state. |
| `reports/ATS_SETTINGS_SCHEMA.json` | DELETE | PROVENANCE_UNKNOWN - NOT ELIGIBLE; reset learned/performance/runtime state. |
| `reports/ATS_STRATEGY_HISTORY_MIGRATION_REPORT.md` | DELETE | PROVENANCE_UNKNOWN - NOT ELIGIBLE; reset learned/performance/runtime state. |
| `reports/ATS_USER_STARTUP_GUIDE.md` | DELETE | Legacy market state |
| `reports/operator-runtime/backend.err.log` | DELETE | Legacy market state |
| `reports/operator-runtime/backend.log` | DELETE | PROVENANCE_UNKNOWN - NOT ELIGIBLE; reset learned/performance/runtime state. |
| `reports/operator-runtime/frontend.err.log` | DELETE | PROVENANCE_UNKNOWN - NOT ELIGIBLE; reset learned/performance/runtime state. |
| `reports/operator-runtime/frontend.log` | DELETE | PROVENANCE_UNKNOWN - NOT ELIGIBLE; reset learned/performance/runtime state. |
| `reports/operator-runtime/processes.json` | DELETE | PROVENANCE_UNKNOWN - NOT ELIGIBLE; reset learned/performance/runtime state. |
| `scripts/.gitkeep` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `scripts/ats-open.ps1` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `scripts/ats-operator.ps1` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `scripts/ats-restart.ps1` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `scripts/ats-start.ps1` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `scripts/ats-status.ps1` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `scripts/ats-stop.ps1` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `scripts/baseline_research_nifty.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `scripts/ci/assert_critical_tests_ran.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `scripts/comprehensive_ats_acceptance.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `scripts/cost_stress_check.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `scripts/evolve_families.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `scripts/probe_diverse_families.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `scripts/run_paper_sessions.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `scripts/start_ats_a2_live_paper.ps1` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `scripts/test_chart360_atomic_audit.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `scripts/test_dynamic_datasets_and_chart360.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `scripts/test_laya_integration.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `scripts/test_lc1_live_streaming_acceptance.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `scripts/test_ui_interactions.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `scripts/validate_strategies.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/__init__.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/acceptance/.gitkeep` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/contract/.gitkeep` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/contract/__init__.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/contract/agents/__init__.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/contract/agents/test_managed_agent_boundary.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/contract/api/test_api_architecture.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/contract/api/test_console_boundary.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `tests/contract/api/test_openapi.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/contract/architecture/__init__.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/contract/architecture/test_source_ownership.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/contract/domain/field_coverage.json` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/contract/domain/test_contracts.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/contract/domain/test_field_coverage.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/contract/events/event_catalogue.json` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/contract/events/golden_chain.json` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/contract/events/test_chain.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/contract/events/test_registry.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/contract/execution/lifecycle/test_d06_state_contract.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/contract/execution/test_d05_durability_matrix.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/contract/governance/__init__.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/contract/governance/continuous/test_interrupt_contract.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/contract/governance/opportunity/test_candidate_contract.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/contract/governance/position/test_position_thesis_contract.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/contract/governance/test_contracts.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/contract/intelligence/__init__.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/contract/intelligence/advisory/test_advisory_boundary.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/contract/intelligence/ensemble/test_ensemble_contract.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/contract/intelligence/formula_runtime/test_contract.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/contract/intelligence/iba_contract_registry.json` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/contract/intelligence/iba_field_coverage.json` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/contract/intelligence/iba_state_transitions.json` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/contract/intelligence/regime/test_regime_contract.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/contract/intelligence/test_iba_evidence.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/contract/intelligence/test_state_machines.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/contract/kernel/test_architecture.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/contract/kernel/test_two_stage.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/contract/market/derivatives/acquisition/test_d03_read_only_contract.py` | REVIEW | Trace core references; remove acquisition/options logic and replace runtime instrument seam. |
| `tests/contract/market/derivatives/normalization/test_d02_contract.py` | REVIEW | Trace core references; remove acquisition/options logic and replace runtime instrument seam. |
| `tests/contract/market/derivatives/providers/test_provider_boundary.py` | REVIEW | Trace core references; remove acquisition/options logic and replace runtime instrument seam. |
| `tests/contract/market/derivatives/test_contract_master_schema.py` | REVIEW | Trace core references; remove acquisition/options logic and replace runtime instrument seam. |
| `tests/contract/market/derivatives/test_option_chain_contract.py` | REVIEW | Trace core references; remove acquisition/options logic and replace runtime instrument seam. |
| `tests/contract/market/golden_replay.json` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/contract/market/intelligence_cache/test_d04_read_only_cache.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/contract/market/test_fixture_contract.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/contract/market/test_history_contract.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/contract/market/test_history_gating_enforcement.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/contract/market/test_market_contract.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `tests/contract/market/test_market_scope.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/contract/persistence/test_schema_contract.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/contract/test_serialization.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/contract/trading_runtime/__init__.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/contract/trading_runtime/test_exit_authority_boundary.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `tests/e2e/.gitkeep` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/faults/.gitkeep` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/faults/market_history/__init__.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/faults/market_history/test_faults.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `tests/faults/persistence/conftest.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/faults/persistence/test_capital_reservation_race.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/faults/persistence/test_postgres_faults.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/faults/strategy_lab/test_faults.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/faults/trading_runtime_faults/__init__.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/faults/trading_runtime_faults/test_runtime_faults.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `tests/integration/.gitkeep` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/integration/__init__.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/integration/api/test_endpoints.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/integration/execution/lifecycle/conftest.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/integration/execution/lifecycle/test_d06_r17_journal.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/integration/execution/paper/test_paper_order_lifecycle.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/integration/forecast/test_kronos_adapter.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/integration/governance/campaign/test_campaign_lifecycle.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/integration/governance/opportunity/test_evidence_flow.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/integration/governance/position/test_position_evidence_flow.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/integration/intelligence/calibration/test_r05_r06_pipeline.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/integration/intelligence/ensemble/test_r04_r05_pipeline.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/integration/intelligence/instrument_selector/test_option_selection_pipeline.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/integration/intelligence/regime/test_r01_r02_pipeline.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/integration/intelligence/strategy_lab/test_walk_forward.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `tests/integration/intelligence/thesis/test_r06_r07_pipeline.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/integration/market/derivatives/active_window/test_d02_d04_integration.py` | REVIEW | Trace core references; remove acquisition/options logic and replace runtime instrument seam. |
| `tests/integration/market/derivatives/fixtures/nse_index_derivatives_20260824.csv` | REVIEW | Trace core references; remove acquisition/options logic and replace runtime instrument seam. |
| `tests/integration/market/derivatives/test_contract_master_fixture.py` | REVIEW | Trace core references; remove acquisition/options logic and replace runtime instrument seam. |
| `tests/integration/market/derivatives/test_end_to_end_readiness.py` | REVIEW | Trace core references; remove acquisition/options logic and replace runtime instrument seam. |
| `tests/integration/market/derivatives/test_option_chain_pipeline.py` | REVIEW | Trace core references; remove acquisition/options logic and replace runtime instrument seam. |
| `tests/integration/market/features/golden_feature_bundle.json` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/integration/market/features/test_b01_feature_pipeline.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/integration/market/history/test_b01_history_integration.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/integration/market/replay/test_full_replay.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/integration/persistence/conftest.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/integration/persistence/test_capital_reservations.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `tests/integration/persistence/test_postgres_store.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/integration/persistence/test_reduction_authority_evidence.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `tests/integration/portfolio/runtime/conftest.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/integration/portfolio/runtime/test_d05_postgres_actor.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `tests/integration/portfolio/runtime/test_d074_postgres_recovery.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `tests/integration/trading_runtime/__init__.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/integration/trading_runtime/paper_fill_seed.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/integration/trading_runtime/test_authority_steel_thread.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/integration/trading_runtime/test_engine_authority_integration.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `tests/integration/trading_runtime/test_multi_position_authority.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `tests/integration/trading_runtime/test_position_authority_postgres.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/integration/trading_runtime/test_reduction_authority_postgres.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `tests/property/.gitkeep` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/property/contracts/iba/__init__.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/property/contracts/iba/test_invariants.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/property/execution/paper/test_paper_properties.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/property/forecast/test_cutoff_invariance.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/property/governance/campaign/test_campaign_properties.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/property/governance/continuous/test_continuous_properties.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/property/governance/opportunity/test_opportunity_properties.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/property/governance/position/test_position_properties.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/property/intelligence/advisory/test_advisory_properties.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/property/intelligence/calibration/test_calibration_properties.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/property/intelligence/ensemble/test_ensemble_properties.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/property/intelligence/formula/test_formula_determinism.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/property/intelligence/instrument_selector/test_selector_properties.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/property/intelligence/regime/test_regime_properties.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/property/intelligence/strategy_lab/test_strategy_lab_determinism.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `tests/property/intelligence/thesis/test_thesis_properties.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/property/kernel/test_constraints.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/property/kernel/test_determinism.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/property/market/derivatives/active_window/test_d04_window_properties.py` | REVIEW | Trace core references; remove acquisition/options logic and replace runtime instrument seam. |
| `tests/property/market/derivatives/contract_master/test_contract_master_properties.py` | REVIEW | Trace core references; remove acquisition/options logic and replace runtime instrument seam. |
| `tests/property/market/derivatives/normalization/test_canonical_stability.py` | REVIEW | Trace core references; remove acquisition/options logic and replace runtime instrument seam. |
| `tests/property/market/derivatives/option_chain/test_option_chain_properties.py` | REVIEW | Trace core references; remove acquisition/options logic and replace runtime instrument seam. |
| `tests/property/market/derivatives/replay_data/test_d03_temporal_properties.py` | REVIEW | Trace core references; remove acquisition/options logic and replace runtime instrument seam. |
| `tests/property/market/features/test_feature_properties.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/property/market/history/test_history_properties.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/property/market/replay/test_properties.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/smoke/test_bootstrap.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/smoke/test_scope.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/unit/.gitkeep` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/unit/__init__.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/unit/api/__init__.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/unit/api/fixtures.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/unit/api/test_read_models.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/unit/api/test_stream.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/unit/contracts/__init__.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/unit/contracts/domain/__init__.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/unit/contracts/domain/fixtures.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `tests/unit/contracts/domain/test_models.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/unit/contracts/events/__init__.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/unit/contracts/events/fixtures.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/unit/contracts/events/test_events.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/unit/contracts/governance/__init__.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/unit/contracts/governance/test_models.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/unit/contracts/intelligence/__init__.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/unit/contracts/intelligence/fixtures.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `tests/unit/contracts/intelligence/test_models.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/unit/contracts/test_common.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/unit/execution/lifecycle/__init__.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/unit/execution/lifecycle/test_machine.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/unit/execution/paper/__init__.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/unit/execution/paper/helpers.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `tests/unit/execution/paper/test_broker.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/unit/forecast/__init__.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/unit/forecast/fixtures.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/unit/forecast/test_naive_worker.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/unit/forecast/test_validation.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/unit/governance/campaign/__init__.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/unit/governance/campaign/helpers.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/unit/governance/campaign/test_runtime.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/unit/governance/continuous/test_runtime.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/unit/governance/opportunity/helpers.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/unit/governance/opportunity/test_governor.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/unit/governance/position/helpers.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/unit/governance/position/test_position_governor.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/unit/intelligence/advisory/test_position_context.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/unit/intelligence/calibration/__init__.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/unit/intelligence/calibration/helpers.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/unit/intelligence/calibration/test_engine.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/unit/intelligence/ensemble/__init__.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/unit/intelligence/ensemble/helpers.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `tests/unit/intelligence/ensemble/test_engine.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/unit/intelligence/formula/test_evaluator.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/unit/intelligence/formula/test_safety.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/unit/intelligence/harness/test_harness_runtime.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/unit/intelligence/inference/test_openrouter.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/unit/intelligence/instrument_selector/__init__.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/unit/intelligence/instrument_selector/helpers.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/unit/intelligence/instrument_selector/test_selector.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/unit/intelligence/regime/__init__.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/unit/intelligence/regime/helpers.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `tests/unit/intelligence/regime/test_detector.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/unit/intelligence/strategy_lab/test_backtest_semantics.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `tests/unit/intelligence/strategy_lab/test_cost_economics.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `tests/unit/intelligence/strategy_lab/test_dataset_binding.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/unit/intelligence/strategy_lab/test_fill_slippage.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `tests/unit/intelligence/strategy_lab/test_leakage_enforcement.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `tests/unit/intelligence/strategy_lab/test_leakage_scanner.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/unit/intelligence/strategy_lab/test_promotion_gate.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/unit/intelligence/strategy_lab/test_promotion_risk.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/unit/intelligence/strategy_lab/test_scorecard.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/unit/intelligence/thesis/__init__.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/unit/intelligence/thesis/helpers.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/unit/intelligence/thesis/test_synthesis.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/unit/kernel/__init__.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/unit/kernel/fixtures.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/unit/kernel/test_gates_token.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/unit/kernel/test_order_guard.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/unit/kernel/test_policy_action.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/unit/kernel/test_reduction_eligibility.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/unit/market/__init__.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/unit/market/data_acquisition/test_real_session_ingestion.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `tests/unit/market/derivatives/__init__.py` | REVIEW | Trace core references; remove acquisition/options logic and replace runtime instrument seam. |
| `tests/unit/market/derivatives/acquisition/test_client.py` | REVIEW | Trace core references; remove acquisition/options logic and replace runtime instrument seam. |
| `tests/unit/market/derivatives/acquisition/test_parsers.py` | REVIEW | Trace core references; remove acquisition/options logic and replace runtime instrument seam. |
| `tests/unit/market/derivatives/acquisition/test_plan.py` | REVIEW | Trace core references; remove acquisition/options logic and replace runtime instrument seam. |
| `tests/unit/market/derivatives/acquisition/test_redaction.py` | REVIEW | Trace core references; remove acquisition/options logic and replace runtime instrument seam. |
| `tests/unit/market/derivatives/acquisition/test_secrets.py` | REVIEW | Trace core references; remove acquisition/options logic and replace runtime instrument seam. |
| `tests/unit/market/derivatives/active_window/__init__.py` | REVIEW | Trace core references; remove acquisition/options logic and replace runtime instrument seam. |
| `tests/unit/market/derivatives/active_window/test_cache.py` | REVIEW | Trace core references; remove acquisition/options logic and replace runtime instrument seam. |
| `tests/unit/market/derivatives/active_window/test_engine.py` | REVIEW | Trace core references; remove acquisition/options logic and replace runtime instrument seam. |
| `tests/unit/market/derivatives/artifacts/test_artifact_provenance.py` | REVIEW | Trace core references; remove acquisition/options logic and replace runtime instrument seam. |
| `tests/unit/market/derivatives/artifacts/test_store.py` | REVIEW | Trace core references; remove acquisition/options logic and replace runtime instrument seam. |
| `tests/unit/market/derivatives/contract_master/__init__.py` | REVIEW | Trace core references; remove acquisition/options logic and replace runtime instrument seam. |
| `tests/unit/market/derivatives/contract_master/expiry_helpers.py` | REVIEW | Trace core references; remove acquisition/options logic and replace runtime instrument seam. |
| `tests/unit/market/derivatives/contract_master/helpers.py` | REVIEW | Trace core references; remove acquisition/options logic and replace runtime instrument seam. |
| `tests/unit/market/derivatives/contract_master/test_expiry_engine.py` | REVIEW | Trace core references; remove acquisition/options logic and replace runtime instrument seam. |
| `tests/unit/market/derivatives/contract_master/test_normalization.py` | REVIEW | Trace core references; remove acquisition/options logic and replace runtime instrument seam. |
| `tests/unit/market/derivatives/contract_master/test_registry.py` | REVIEW | Trace core references; remove acquisition/options logic and replace runtime instrument seam. |
| `tests/unit/market/derivatives/normalization/test_normalizer.py` | REVIEW | Trace core references; remove acquisition/options logic and replace runtime instrument seam. |
| `tests/unit/market/derivatives/option_chain/__init__.py` | REVIEW | Trace core references; remove acquisition/options logic and replace runtime instrument seam. |
| `tests/unit/market/derivatives/option_chain/helpers.py` | REVIEW | Trace core references; remove acquisition/options logic and replace runtime instrument seam. |
| `tests/unit/market/derivatives/option_chain/test_builder.py` | REVIEW | Trace core references; remove acquisition/options logic and replace runtime instrument seam. |
| `tests/unit/market/derivatives/option_chain/test_features.py` | REVIEW | Trace core references; remove acquisition/options logic and replace runtime instrument seam. |
| `tests/unit/market/derivatives/option_chain/test_greeks_calculator.py` | REVIEW | Trace core references; remove acquisition/options logic and replace runtime instrument seam. |
| `tests/unit/market/derivatives/providers/test_provenance.py` | REVIEW | Trace core references; remove acquisition/options logic and replace runtime instrument seam. |
| `tests/unit/market/derivatives/replay_data/test_builder.py` | REVIEW | Trace core references; remove acquisition/options logic and replace runtime instrument seam. |
| `tests/unit/market/derivatives/replay_data/test_resampler.py` | REVIEW | Trace core references; remove acquisition/options logic and replace runtime instrument seam. |
| `tests/unit/market/derivatives/strike_window/__init__.py` | REVIEW | Trace core references; remove acquisition/options logic and replace runtime instrument seam. |
| `tests/unit/market/derivatives/strike_window/helpers.py` | REVIEW | Trace core references; remove acquisition/options logic and replace runtime instrument seam. |
| `tests/unit/market/derivatives/strike_window/test_strike_window.py` | REVIEW | Trace core references; remove acquisition/options logic and replace runtime instrument seam. |
| `tests/unit/market/features/__init__.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/unit/market/features/helpers.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `tests/unit/market/features/test_engine_base.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/unit/market/features/test_engine_rolling.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/unit/market/features/test_registry.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/unit/market/feeds/__init__.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/unit/market/feeds/upstox_v3/__init__.py` | DELETE | Obsolete provider implementation, fixtures, tests or provider documentation. |
| `tests/unit/market/feeds/upstox_v3/helpers.py` | DELETE | Obsolete provider implementation, fixtures, tests or provider documentation. |
| `tests/unit/market/feeds/upstox_v3/test_adapter.py` | DELETE | Obsolete provider implementation, fixtures, tests or provider documentation. |
| `tests/unit/market/feeds/upstox_v3/test_codec.py` | DELETE | Obsolete provider implementation, fixtures, tests or provider documentation. |
| `tests/unit/market/feeds/upstox_v3/test_frames.py` | DELETE | Obsolete provider implementation, fixtures, tests or provider documentation. |
| `tests/unit/market/feeds/upstox_v3/test_freshness.py` | DELETE | Obsolete provider implementation, fixtures, tests or provider documentation. |
| `tests/unit/market/feeds/upstox_v3/test_protobuf_codec.py` | DELETE | Obsolete provider implementation, fixtures, tests or provider documentation. |
| `tests/unit/market/feeds/upstox_v3/test_subscription.py` | DELETE | Obsolete provider implementation, fixtures, tests or provider documentation. |
| `tests/unit/market/feeds/upstox_v3/test_transport.py` | DELETE | Obsolete provider implementation, fixtures, tests or provider documentation. |
| `tests/unit/market/fixtures.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/unit/market/history/__init__.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/unit/market/history/fixtures.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `tests/unit/market/history/test_as_of.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `tests/unit/market/history/test_bridge_derivatives.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `tests/unit/market/history/test_calendar_policy.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/unit/market/history/test_manifest_dataset.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/unit/market/history/test_models.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `tests/unit/market/history/test_policy_overrides.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `tests/unit/market/history/test_storage.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/unit/market/history/test_timeline.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/unit/market/history/test_validation.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/unit/market/intelligence_cache/test_cache.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `tests/unit/market/providers/upstox/test_capabilities.py` | DELETE | Obsolete provider implementation, fixtures, tests or provider documentation. |
| `tests/unit/market/test_calendar.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/unit/market/test_manifest_fixture.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `tests/unit/market/test_replay.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `tests/unit/persistence/test_capital_models.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/unit/persistence/test_interfaces.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/unit/portfolio/runtime/__init__.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/unit/portfolio/runtime/helpers.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `tests/unit/portfolio/runtime/test_actor.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `tests/unit/trading_runtime/__init__.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/unit/trading_runtime/exit_authorization_doubles.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/unit/trading_runtime/helpers.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `tests/unit/trading_runtime/test_autonomous_acceptance.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `tests/unit/trading_runtime/test_broker_autofill.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `tests/unit/trading_runtime/test_compound_failures.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `tests/unit/trading_runtime/test_exit_authorization_failures.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `tests/unit/trading_runtime/test_forward_validation.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `tests/unit/trading_runtime/test_orchestrator.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `tests/unit/trading_runtime/test_reconciliation.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/unit/trading_runtime/test_shutdown.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `tests/unit/trading_runtime/test_startup.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `tests/unit/trading_runtime_tests/__init__.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/unit/trading_runtime_tests/test_anti_churn.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `tests/unit/trading_runtime_tests/test_browser_handoff.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `tests/unit/trading_runtime_tests/test_candidate_factory.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `tests/unit/trading_runtime_tests/test_capital_stops.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `tests/unit/trading_runtime_tests/test_directional_churn.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `tests/unit/trading_runtime_tests/test_engine.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `tests/unit/trading_runtime_tests/test_exit_pipeline.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `tests/unit/trading_runtime_tests/test_hwm.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/unit/trading_runtime_tests/test_intelligence_pipeline.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `tests/unit/trading_runtime_tests/test_lot_size.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `tests/unit/trading_runtime_tests/test_mark_update.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `tests/unit/trading_runtime_tests/test_mode_enforcement.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `tests/unit/trading_runtime_tests/test_modes.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/unit/trading_runtime_tests/test_position_monitor.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `tests/unit/trading_runtime_tests/test_safety.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/unit/trading_runtime_tests/test_session.py` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `tests/unit/trading_runtime_tests/test_spread_gating.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |
| `toolchain.json` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `uv.lock` | KEEP GENERIC | No legacy reference found; subject to dependency audit. |
| `verify_all_features.py` | REWRITE FOR XAUUSD | Legacy assumptions or identifiers; retain only useful generic behavior. |

## Reviewed deletion decisions before purge

Recovery ZIP verified against all 1,012 original file hashes. The following reviewed paths are DELETE. Generic strategy source is relocated before persona removal. Core authorization algorithms are retained.

- `ATS_BASELINE_STATUS.md`: DELETE
- `ATS_FEED_RESILIENCE_REPORT.md`: DELETE
- `ATS_HISTORY_LIVE_RECONCILIATION.md`: DELETE
- `ATS_LC1_BASELINE.md`: DELETE
- `ATS_LC1_FINAL_REPORT.md`: DELETE
- `ATS_LC1_MANIFEST.json`: DELETE
- `ATS_LC1_SECURITY_REPORT.md`: DELETE
- `ATS_LC1_TEST_REPORT.md`: DELETE
- `ATS_LIVE_CANDLE_ENGINE_SPEC.md`: DELETE
- `ATS_LIVE_CHART_ACCEPTANCE.md`: DELETE
- `ATS_LIVE_PROVIDER_ARCHITECTURE.md`: DELETE
- `ATS_MARKET_DATA_OBSERVABILITY.md`: DELETE
- `ATS_NORMALIZED_MARKET_EVENT_SPEC.md`: DELETE
- `ATS_STREAM_HUB_SPEC.md`: DELETE
- `ATS_UPSTOX_V3_STREAM_REPORT.md`: DELETE
- `backend/src/ats/agents/config.py`: DELETE
- `backend/src/ats/agents/costs.py`: DELETE
- `backend/src/ats/agents/custom.py`: DELETE
- `backend/src/ats/agents/deployment.py`: DELETE
- `backend/src/ats/agents/edge.py`: DELETE
- `backend/src/ats/agents/evolver.py`: DELETE
- `backend/src/ats/agents/execution.py`: DELETE
- `backend/src/ats/agents/families.py`: DELETE
- `backend/src/ats/agents/features.py`: DELETE
- `backend/src/ats/agents/portfolio.py`: DELETE
- `backend/src/ats/agents/risk.py`: DELETE
- `backend/src/ats/agents/roster.py`: DELETE
- `backend/src/ats/agents/router.py`: DELETE
- `backend/src/ats/agents/strategies.py`: DELETE
- `backend/src/ats/agents/trade_ledger.py`: DELETE
- `backend/src/ats/agents/worker.py`: DELETE
- `backend/src/ats/ai/capital_advisor.py`: DELETE
- `backend/src/ats/ai/live_coach.py`: DELETE
- `backend/src/ats/console/governance_router.py`: DELETE
- `backend/src/ats/console/imported_strategies_router.py`: DELETE
- `backend/src/ats/console/laya_router.py`: DELETE
- `backend/src/ats/console/settings_router.py`: DELETE
- `backend/src/ats/console/strategy_lab_router.py`: DELETE
- `backend/src/ats/market/data_acquisition/__init__.py`: DELETE
- `backend/src/ats/market/data_acquisition/__pycache__/__init__.cpython-311.pyc`: DELETE
- `backend/src/ats/market/data_acquisition/__pycache__/ingest_session.cpython-311.pyc`: DELETE
- `backend/src/ats/market/data_acquisition/__pycache__/upstox_client.cpython-311.pyc`: DELETE
- `backend/src/ats/market/data_acquisition/ingest_session.py`: DELETE
- `backend/src/ats/market/data_acquisition/upstox_client.py`: DELETE
- `backend/src/ats/market/derivatives/__init__.py`: DELETE
- `backend/src/ats/market/derivatives/__pycache__/__init__.cpython-311.pyc`: DELETE
- `backend/src/ats/market/derivatives/__pycache__/__init__.cpython-313.pyc`: DELETE
- `backend/src/ats/market/derivatives/__pycache__/__init__.cpython-314.pyc`: DELETE
- `backend/src/ats/market/derivatives/acquisition/__init__.py`: DELETE
- `backend/src/ats/market/derivatives/acquisition/__pycache__/__init__.cpython-311.pyc`: DELETE
- `backend/src/ats/market/derivatives/acquisition/__pycache__/client.cpython-311.pyc`: DELETE
- `backend/src/ats/market/derivatives/acquisition/__pycache__/models.cpython-311.pyc`: DELETE
- `backend/src/ats/market/derivatives/acquisition/__pycache__/parsers.cpython-311.pyc`: DELETE
- `backend/src/ats/market/derivatives/acquisition/__pycache__/plan.cpython-311.pyc`: DELETE
- `backend/src/ats/market/derivatives/acquisition/__pycache__/redaction.cpython-311.pyc`: DELETE
- `backend/src/ats/market/derivatives/acquisition/__pycache__/secrets.cpython-311.pyc`: DELETE
- `backend/src/ats/market/derivatives/acquisition/client.py`: DELETE
- `backend/src/ats/market/derivatives/acquisition/models.py`: DELETE
- `backend/src/ats/market/derivatives/acquisition/parsers.py`: DELETE
- `backend/src/ats/market/derivatives/acquisition/plan.py`: DELETE
- `backend/src/ats/market/derivatives/acquisition/redaction.py`: DELETE
- `backend/src/ats/market/derivatives/acquisition/secrets.py`: DELETE
- `backend/src/ats/market/derivatives/active_window/__init__.py`: DELETE
- `backend/src/ats/market/derivatives/active_window/__pycache__/__init__.cpython-311.pyc`: DELETE
- `backend/src/ats/market/derivatives/active_window/__pycache__/cache.cpython-311.pyc`: DELETE
- `backend/src/ats/market/derivatives/active_window/__pycache__/engine.cpython-311.pyc`: DELETE
- `backend/src/ats/market/derivatives/active_window/__pycache__/models.cpython-311.pyc`: DELETE
- `backend/src/ats/market/derivatives/active_window/cache.py`: DELETE
- `backend/src/ats/market/derivatives/active_window/engine.py`: DELETE
- `backend/src/ats/market/derivatives/active_window/models.py`: DELETE
- `backend/src/ats/market/derivatives/artifacts/__init__.py`: DELETE
- `backend/src/ats/market/derivatives/artifacts/__pycache__/__init__.cpython-311.pyc`: DELETE
- `backend/src/ats/market/derivatives/artifacts/__pycache__/models.cpython-311.pyc`: DELETE
- `backend/src/ats/market/derivatives/artifacts/__pycache__/provenance.cpython-311.pyc`: DELETE
- `backend/src/ats/market/derivatives/artifacts/__pycache__/store.cpython-311.pyc`: DELETE
- `backend/src/ats/market/derivatives/artifacts/models.py`: DELETE
- `backend/src/ats/market/derivatives/artifacts/provenance.py`: DELETE
- `backend/src/ats/market/derivatives/artifacts/store.py`: DELETE
- `backend/src/ats/market/derivatives/contract_master/__init__.py`: DELETE
- `backend/src/ats/market/derivatives/contract_master/__pycache__/__init__.cpython-311.pyc`: DELETE
- `backend/src/ats/market/derivatives/contract_master/__pycache__/__init__.cpython-313.pyc`: DELETE
- `backend/src/ats/market/derivatives/contract_master/__pycache__/__init__.cpython-314.pyc`: DELETE
- `backend/src/ats/market/derivatives/contract_master/__pycache__/errors.cpython-311.pyc`: DELETE
- `backend/src/ats/market/derivatives/contract_master/__pycache__/errors.cpython-313.pyc`: DELETE
- `backend/src/ats/market/derivatives/contract_master/__pycache__/errors.cpython-314.pyc`: DELETE
- `backend/src/ats/market/derivatives/contract_master/__pycache__/expiry.cpython-311.pyc`: DELETE
- `backend/src/ats/market/derivatives/contract_master/__pycache__/expiry.cpython-313.pyc`: DELETE
- `backend/src/ats/market/derivatives/contract_master/__pycache__/expiry.cpython-314.pyc`: DELETE
- `backend/src/ats/market/derivatives/contract_master/__pycache__/models.cpython-311.pyc`: DELETE
- `backend/src/ats/market/derivatives/contract_master/__pycache__/models.cpython-313.pyc`: DELETE
- `backend/src/ats/market/derivatives/contract_master/__pycache__/models.cpython-314.pyc`: DELETE
- `backend/src/ats/market/derivatives/contract_master/__pycache__/normalization.cpython-311.pyc`: DELETE
- `backend/src/ats/market/derivatives/contract_master/__pycache__/normalization.cpython-313.pyc`: DELETE
- `backend/src/ats/market/derivatives/contract_master/__pycache__/normalization.cpython-314.pyc`: DELETE
- `backend/src/ats/market/derivatives/contract_master/__pycache__/registry.cpython-311.pyc`: DELETE
- `backend/src/ats/market/derivatives/contract_master/__pycache__/registry.cpython-313.pyc`: DELETE
- `backend/src/ats/market/derivatives/contract_master/__pycache__/registry.cpython-314.pyc`: DELETE
- `backend/src/ats/market/derivatives/contract_master/errors.py`: DELETE
- `backend/src/ats/market/derivatives/contract_master/expiry.py`: DELETE
- `backend/src/ats/market/derivatives/contract_master/models.py`: DELETE
- `backend/src/ats/market/derivatives/contract_master/normalization.py`: DELETE
- `backend/src/ats/market/derivatives/contract_master/registry.py`: DELETE
- `backend/src/ats/market/derivatives/normalization/__init__.py`: DELETE
- `backend/src/ats/market/derivatives/normalization/__pycache__/__init__.cpython-311.pyc`: DELETE
- `backend/src/ats/market/derivatives/normalization/__pycache__/models.cpython-311.pyc`: DELETE
- `backend/src/ats/market/derivatives/normalization/__pycache__/normalizer.cpython-311.pyc`: DELETE
- `backend/src/ats/market/derivatives/normalization/models.py`: DELETE
- `backend/src/ats/market/derivatives/normalization/normalizer.py`: DELETE
- `backend/src/ats/market/derivatives/option_chain/__init__.py`: DELETE
- `backend/src/ats/market/derivatives/option_chain/__pycache__/__init__.cpython-311.pyc`: DELETE
- `backend/src/ats/market/derivatives/option_chain/__pycache__/__init__.cpython-313.pyc`: DELETE
- `backend/src/ats/market/derivatives/option_chain/__pycache__/__init__.cpython-314.pyc`: DELETE
- `backend/src/ats/market/derivatives/option_chain/__pycache__/builder.cpython-311.pyc`: DELETE
- `backend/src/ats/market/derivatives/option_chain/__pycache__/builder.cpython-313.pyc`: DELETE
- `backend/src/ats/market/derivatives/option_chain/__pycache__/builder.cpython-314.pyc`: DELETE
- `backend/src/ats/market/derivatives/option_chain/__pycache__/errors.cpython-311.pyc`: DELETE
- `backend/src/ats/market/derivatives/option_chain/__pycache__/errors.cpython-313.pyc`: DELETE
- `backend/src/ats/market/derivatives/option_chain/__pycache__/errors.cpython-314.pyc`: DELETE
- `backend/src/ats/market/derivatives/option_chain/__pycache__/features.cpython-311.pyc`: DELETE
- `backend/src/ats/market/derivatives/option_chain/__pycache__/features.cpython-313.pyc`: DELETE
- `backend/src/ats/market/derivatives/option_chain/__pycache__/features.cpython-314.pyc`: DELETE
- `backend/src/ats/market/derivatives/option_chain/__pycache__/greeks_calculator.cpython-311.pyc`: DELETE
- `backend/src/ats/market/derivatives/option_chain/__pycache__/greeks_calculator.cpython-313.pyc`: DELETE
- `backend/src/ats/market/derivatives/option_chain/__pycache__/greeks_calculator.cpython-314.pyc`: DELETE
- `backend/src/ats/market/derivatives/option_chain/__pycache__/models.cpython-311.pyc`: DELETE
- `backend/src/ats/market/derivatives/option_chain/__pycache__/models.cpython-313.pyc`: DELETE
- `backend/src/ats/market/derivatives/option_chain/__pycache__/models.cpython-314.pyc`: DELETE
- `backend/src/ats/market/derivatives/option_chain/builder.py`: DELETE
- `backend/src/ats/market/derivatives/option_chain/errors.py`: DELETE
- `backend/src/ats/market/derivatives/option_chain/features.py`: DELETE
- `backend/src/ats/market/derivatives/option_chain/greeks_calculator.py`: DELETE
- `backend/src/ats/market/derivatives/option_chain/models.py`: DELETE
- `backend/src/ats/market/derivatives/providers/__init__.py`: DELETE
- `backend/src/ats/market/derivatives/providers/__pycache__/__init__.cpython-311.pyc`: DELETE
- `backend/src/ats/market/derivatives/providers/__pycache__/__init__.cpython-313.pyc`: DELETE
- `backend/src/ats/market/derivatives/providers/__pycache__/__init__.cpython-314.pyc`: DELETE
- `backend/src/ats/market/derivatives/providers/__pycache__/models.cpython-311.pyc`: DELETE
- `backend/src/ats/market/derivatives/providers/__pycache__/models.cpython-313.pyc`: DELETE
- `backend/src/ats/market/derivatives/providers/__pycache__/models.cpython-314.pyc`: DELETE
- `backend/src/ats/market/derivatives/providers/__pycache__/protocols.cpython-311.pyc`: DELETE
- `backend/src/ats/market/derivatives/providers/__pycache__/protocols.cpython-313.pyc`: DELETE
- `backend/src/ats/market/derivatives/providers/__pycache__/protocols.cpython-314.pyc`: DELETE
- `backend/src/ats/market/derivatives/providers/models.py`: DELETE
- `backend/src/ats/market/derivatives/providers/protocols.py`: DELETE
- `backend/src/ats/market/derivatives/replay_data/__init__.py`: DELETE
- `backend/src/ats/market/derivatives/replay_data/__pycache__/__init__.cpython-311.pyc`: DELETE
- `backend/src/ats/market/derivatives/replay_data/__pycache__/builder.cpython-311.pyc`: DELETE
- `backend/src/ats/market/derivatives/replay_data/__pycache__/models.cpython-311.pyc`: DELETE
- `backend/src/ats/market/derivatives/replay_data/__pycache__/resampler.cpython-311.pyc`: DELETE
- `backend/src/ats/market/derivatives/replay_data/builder.py`: DELETE
- `backend/src/ats/market/derivatives/replay_data/models.py`: DELETE
- `backend/src/ats/market/derivatives/replay_data/resampler.py`: DELETE
- `backend/src/ats/market/derivatives/strike_window/__init__.py`: DELETE
- `backend/src/ats/market/derivatives/strike_window/__pycache__/__init__.cpython-311.pyc`: DELETE
- `backend/src/ats/market/derivatives/strike_window/__pycache__/engine.cpython-311.pyc`: DELETE
- `backend/src/ats/market/derivatives/strike_window/__pycache__/errors.cpython-311.pyc`: DELETE
- `backend/src/ats/market/derivatives/strike_window/__pycache__/models.cpython-311.pyc`: DELETE
- `backend/src/ats/market/derivatives/strike_window/engine.py`: DELETE
- `backend/src/ats/market/derivatives/strike_window/errors.py`: DELETE
- `backend/src/ats/market/derivatives/strike_window/models.py`: DELETE
- `backend/src/ats/market/feeds/upstox_v3/__init__.py`: DELETE
- `backend/src/ats/market/feeds/upstox_v3/__pycache__/__init__.cpython-311.pyc`: DELETE
- `backend/src/ats/market/feeds/upstox_v3/__pycache__/__init__.cpython-313.pyc`: DELETE
- `backend/src/ats/market/feeds/upstox_v3/__pycache__/__init__.cpython-314.pyc`: DELETE
- `backend/src/ats/market/feeds/upstox_v3/__pycache__/adapter.cpython-311.pyc`: DELETE
- `backend/src/ats/market/feeds/upstox_v3/__pycache__/adapter.cpython-313.pyc`: DELETE
- `backend/src/ats/market/feeds/upstox_v3/__pycache__/adapter.cpython-314.pyc`: DELETE
- `backend/src/ats/market/feeds/upstox_v3/__pycache__/codec.cpython-311.pyc`: DELETE
- `backend/src/ats/market/feeds/upstox_v3/__pycache__/codec.cpython-313.pyc`: DELETE
- `backend/src/ats/market/feeds/upstox_v3/__pycache__/codec.cpython-314.pyc`: DELETE
- `backend/src/ats/market/feeds/upstox_v3/__pycache__/config.cpython-311.pyc`: DELETE
- `backend/src/ats/market/feeds/upstox_v3/__pycache__/config.cpython-313.pyc`: DELETE
- `backend/src/ats/market/feeds/upstox_v3/__pycache__/config.cpython-314.pyc`: DELETE
- `backend/src/ats/market/feeds/upstox_v3/__pycache__/errors.cpython-311.pyc`: DELETE
- `backend/src/ats/market/feeds/upstox_v3/__pycache__/errors.cpython-313.pyc`: DELETE
- `backend/src/ats/market/feeds/upstox_v3/__pycache__/errors.cpython-314.pyc`: DELETE
- `backend/src/ats/market/feeds/upstox_v3/__pycache__/frames.cpython-311.pyc`: DELETE
- `backend/src/ats/market/feeds/upstox_v3/__pycache__/frames.cpython-313.pyc`: DELETE
- `backend/src/ats/market/feeds/upstox_v3/__pycache__/frames.cpython-314.pyc`: DELETE
- `backend/src/ats/market/feeds/upstox_v3/__pycache__/freshness.cpython-311.pyc`: DELETE
- `backend/src/ats/market/feeds/upstox_v3/__pycache__/freshness.cpython-313.pyc`: DELETE
- `backend/src/ats/market/feeds/upstox_v3/__pycache__/freshness.cpython-314.pyc`: DELETE
- `backend/src/ats/market/feeds/upstox_v3/__pycache__/instrument_keys.cpython-311.pyc`: DELETE
- `backend/src/ats/market/feeds/upstox_v3/__pycache__/instrument_keys.cpython-313.pyc`: DELETE
- `backend/src/ats/market/feeds/upstox_v3/__pycache__/instrument_keys.cpython-314.pyc`: DELETE
- `backend/src/ats/market/feeds/upstox_v3/__pycache__/messages.cpython-311.pyc`: DELETE
- `backend/src/ats/market/feeds/upstox_v3/__pycache__/messages.cpython-313.pyc`: DELETE
- `backend/src/ats/market/feeds/upstox_v3/__pycache__/messages.cpython-314.pyc`: DELETE
- `backend/src/ats/market/feeds/upstox_v3/__pycache__/protobuf_codec.cpython-311.pyc`: DELETE
- `backend/src/ats/market/feeds/upstox_v3/__pycache__/protobuf_codec.cpython-313.pyc`: DELETE
- `backend/src/ats/market/feeds/upstox_v3/__pycache__/protobuf_codec.cpython-314.pyc`: DELETE
- `backend/src/ats/market/feeds/upstox_v3/__pycache__/subscription.cpython-311.pyc`: DELETE
- `backend/src/ats/market/feeds/upstox_v3/__pycache__/subscription.cpython-313.pyc`: DELETE
- `backend/src/ats/market/feeds/upstox_v3/__pycache__/subscription.cpython-314.pyc`: DELETE
- `backend/src/ats/market/feeds/upstox_v3/__pycache__/transport.cpython-311.pyc`: DELETE
- `backend/src/ats/market/feeds/upstox_v3/__pycache__/transport.cpython-313.pyc`: DELETE
- `backend/src/ats/market/feeds/upstox_v3/__pycache__/transport.cpython-314.pyc`: DELETE
- `backend/src/ats/market/feeds/upstox_v3/adapter.py`: DELETE
- `backend/src/ats/market/feeds/upstox_v3/codec.py`: DELETE
- `backend/src/ats/market/feeds/upstox_v3/config.py`: DELETE
- `backend/src/ats/market/feeds/upstox_v3/errors.py`: DELETE
- `backend/src/ats/market/feeds/upstox_v3/frames.py`: DELETE
- `backend/src/ats/market/feeds/upstox_v3/freshness.py`: DELETE
- `backend/src/ats/market/feeds/upstox_v3/instrument_keys.py`: DELETE
- `backend/src/ats/market/feeds/upstox_v3/messages.py`: DELETE
- `backend/src/ats/market/feeds/upstox_v3/proto/MarketDataFeedV3.proto`: DELETE
- `backend/src/ats/market/feeds/upstox_v3/proto/MarketDataFeedV3_pb2.py`: DELETE
- `backend/src/ats/market/feeds/upstox_v3/proto/MarketDataFeedV3_pb2.pyi`: DELETE
- `backend/src/ats/market/feeds/upstox_v3/proto/README.md`: DELETE
- `backend/src/ats/market/feeds/upstox_v3/proto/__init__.py`: DELETE
- `backend/src/ats/market/feeds/upstox_v3/proto/__pycache__/MarketDataFeedV3_pb2.cpython-311.pyc`: DELETE
- `backend/src/ats/market/feeds/upstox_v3/proto/__pycache__/MarketDataFeedV3_pb2.cpython-313.pyc`: DELETE
- `backend/src/ats/market/feeds/upstox_v3/proto/__pycache__/MarketDataFeedV3_pb2.cpython-314.pyc`: DELETE
- `backend/src/ats/market/feeds/upstox_v3/proto/__pycache__/__init__.cpython-311.pyc`: DELETE
- `backend/src/ats/market/feeds/upstox_v3/proto/__pycache__/__init__.cpython-313.pyc`: DELETE
- `backend/src/ats/market/feeds/upstox_v3/proto/__pycache__/__init__.cpython-314.pyc`: DELETE
- `backend/src/ats/market/feeds/upstox_v3/protobuf_codec.py`: DELETE
- `backend/src/ats/market/feeds/upstox_v3/subscription.py`: DELETE
- `backend/src/ats/market/feeds/upstox_v3/transport.py`: DELETE
- `backend/src/ats/market/live/subscriptions.py`: DELETE
- `backend/src/ats/market/live/upstox_v3.py`: DELETE
- `backend/src/ats/market/providers/upstox/__init__.py`: DELETE
- `backend/src/ats/market/providers/upstox/__pycache__/__init__.cpython-311.pyc`: DELETE
- `backend/src/ats/market/providers/upstox/__pycache__/catalogue.cpython-311.pyc`: DELETE
- `backend/src/ats/market/providers/upstox/__pycache__/models.cpython-311.pyc`: DELETE
- `backend/src/ats/market/providers/upstox/__pycache__/protocols.cpython-311.pyc`: DELETE
- `backend/src/ats/market/providers/upstox/__pycache__/rate_limit.cpython-311.pyc`: DELETE
- `backend/src/ats/market/providers/upstox/catalogue.py`: DELETE
- `backend/src/ats/market/providers/upstox/models.py`: DELETE
- `backend/src/ats/market/providers/upstox/protocols.py`: DELETE
- `backend/src/ats/market/providers/upstox/rate_limit.py`: DELETE
- `backend/src/ats/market/strategy_import/__init__.py`: DELETE
- `backend/src/ats/market/strategy_import/__pycache__/__init__.cpython-311.pyc`: DELETE
- `backend/src/ats/market/strategy_import/__pycache__/__init__.cpython-313.pyc`: DELETE
- `backend/src/ats/market/strategy_import/__pycache__/adapters.cpython-311.pyc`: DELETE
- `backend/src/ats/market/strategy_import/__pycache__/adapters.cpython-313.pyc`: DELETE
- `backend/src/ats/market/strategy_import/__pycache__/decoder.cpython-311.pyc`: DELETE
- `backend/src/ats/market/strategy_import/__pycache__/decoder.cpython-313.pyc`: DELETE
- `backend/src/ats/market/strategy_import/__pycache__/models.cpython-311.pyc`: DELETE
- `backend/src/ats/market/strategy_import/__pycache__/models.cpython-313.pyc`: DELETE
- `backend/src/ats/market/strategy_import/__pycache__/tournament.cpython-311.pyc`: DELETE
- `backend/src/ats/market/strategy_import/__pycache__/tournament.cpython-313.pyc`: DELETE
- `backend/src/ats/market/strategy_import/adapters.py`: DELETE
- `backend/src/ats/market/strategy_import/decoder.py`: DELETE
- `backend/src/ats/market/strategy_import/models.py`: DELETE
- `backend/src/ats/market/strategy_import/tournament.py`: DELETE
- `backend/src/ats/optimization/__init__.py`: DELETE
- `backend/src/ats/optimization/__pycache__/__init__.cpython-311.pyc`: DELETE
- `backend/src/ats/optimization/__pycache__/router.cpython-311.pyc`: DELETE
- `backend/src/ats/optimization/__pycache__/worker.cpython-311.pyc`: DELETE
- `backend/src/ats/optimization/router.py`: DELETE
- `backend/src/ats/optimization/worker.py`: DELETE
- `backend/src/ats/strategies/lab_service.py`: DELETE
- `backend/src/data/market_journal/journal_upstox_20260924_07.jsonl`: DELETE
- `backend/src/data/market_journal/journal_upstox_20260924_08.jsonl`: DELETE
- `backend/tests/test_agents_cost_gate.py`: DELETE
- `backend/tests/test_agents_edge_portfolio_execution.py`: DELETE
- `backend/tests/test_agents_market_resolution.py`: DELETE
- `backend/tests/test_agents_playground.py`: DELETE
- `backend/tests/test_agents_risk_api.py`: DELETE
- `backend/tests/test_agents_worker_e2e.py`: DELETE
- `backend/tests/test_datasets_registry.py`: DELETE
- `backend/tests/test_governance_router.py`: DELETE
- `backend/tests/test_live_streaming_engine.py`: DELETE
- `backend/tests/test_paper_control_center.py`: DELETE
- `backend/tests/test_paper_tournament.py`: DELETE
- `backend/tests/test_strategy_import.py`: DELETE
- `data/agents/agents_config.json`: DELETE
- `data/agents/roster.json`: DELETE
- `data/agents/upstox_live_trades_ledger.json`: DELETE
- `data/datasets/datasets_manifest.json`: DELETE
- `data/forward_validation/evidence_ledger.jsonl`: DELETE
- `data/historical/banknifty_options_a2_replay_v1/manifest.json`: DELETE
- `data/historical/banknifty_options_a2_replay_v1/observations.jsonl`: DELETE
- `data/historical/banknifty_options_a2_replay_v1/policy.json`: DELETE
- `data/historical/banknifty_options_a2_replay_v1/records.sha256`: DELETE
- `data/historical/calibration_store_v1.json`: DELETE
- `data/historical/calibration_stores/A1_calibration_store.json`: DELETE
- `data/historical/calibration_stores/A2_calibration_store.json`: DELETE
- `data/historical/calibration_stores/A3_calibration_store.json`: DELETE
- `data/historical/calibration_stores/A4_calibration_store.json`: DELETE
- `data/historical/calibration_stores/C0_calibration_store.json`: DELETE
- `data/historical/calibration_stores/C1_calibration_store.json`: DELETE
- `data/historical/calibration_stores/C2_calibration_store.json`: DELETE
- `data/historical/calibration_stores/C3_calibration_store.json`: DELETE
- `data/historical/calibration_stores/C4_calibration_store.json`: DELETE
- `data/historical/calibration_stores/C5_calibration_store.json`: DELETE
- `data/historical/nifty_options_a2_replay_v1/manifest.json`: DELETE
- `data/historical/nifty_options_a2_replay_v1/observations.jsonl`: DELETE
- `data/historical/nifty_options_a2_replay_v1/policy.json`: DELETE
- `data/historical/nifty_options_a2_replay_v1/records.sha256`: DELETE
- `data/market_journal/journal_upstox_20260923_18.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260924_04.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260924_05.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260924_06.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260924_07.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260924_08.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260924_16.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260924_17.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260924_18.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260924_19.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260924_20.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260924_21.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260924_22.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260924_23.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260925_03.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260925_04.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260925_05.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260925_06.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260925_07.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260925_08.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260925_09.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260925_10.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260925_11.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260925_12.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260925_13.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260925_14.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260925_15.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260925_16.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260925_17.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260925_22.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260926_06.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260926_16.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260927_02.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260927_09.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260927_10.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260927_14.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260927_16.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260927_17.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260927_18.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260927_19.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260928_08.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260928_09.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260928_10.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260928_11.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260928_12.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260928_13.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260928_14.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260928_15.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260928_16.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260928_17.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260929_08.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260929_09.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260929_10.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260930_05.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260930_06.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260930_07.jsonl`: DELETE
- `data/market_journal/journal_upstox_20261001_04.jsonl`: DELETE
- `data/market_journal/journal_upstox_20261001_05.jsonl`: DELETE
- `data/market_journal/journal_upstox_20261001_06.jsonl`: DELETE
- `data/market_journal/journal_upstox_20261001_07.jsonl`: DELETE
- `data/market_journal/journal_upstox_20261001_08.jsonl`: DELETE
- `data/market_journal/journal_upstox_20261001_09.jsonl`: DELETE
- `data/market_journal/journal_upstox_20261001_10.jsonl`: DELETE
- `data/market_journal/journal_upstox_20261003_10.jsonl`: DELETE
- `data/market_journal/journal_upstox_20261003_11.jsonl`: DELETE
- `data/market_journal/journal_upstox_20261004_11.jsonl`: DELETE
- `data/market_journal/journal_upstox_20261005_12.jsonl`: DELETE
- `data/market_journal/journal_upstox_20261005_13.jsonl`: DELETE
- `data/market_journal/journal_upstox_20261005_21.jsonl`: DELETE
- `data/market_journal/journal_upstox_20261006_10.jsonl`: DELETE
- `data/raw/upstox/banknifty_option_chain.json`: DELETE
- `data/raw/upstox/nifty_option_chain.json`: DELETE
- `data/raw/upstox/sessions/2026-08-04/BANKNIFTY_underlying.json`: DELETE
- `data/raw/upstox/sessions/2026-08-04/NIFTY_underlying.json`: DELETE
- `data/raw/upstox/sessions/2026-08-05/BANKNIFTY_underlying.json`: DELETE
- `data/raw/upstox/sessions/2026-08-05/NIFTY_underlying.json`: DELETE
- `data/raw/upstox/sessions/2026-08-06/BANKNIFTY_underlying.json`: DELETE
- `data/raw/upstox/sessions/2026-08-06/NIFTY_underlying.json`: DELETE
- `data/raw/upstox/sessions/2026-08-07/BANKNIFTY_underlying.json`: DELETE
- `data/raw/upstox/sessions/2026-08-07/NIFTY_underlying.json`: DELETE
- `data/raw/upstox/sessions/2026-08-10/BANKNIFTY_underlying.json`: DELETE
- `data/raw/upstox/sessions/2026-08-10/NIFTY_underlying.json`: DELETE
- `data/raw/upstox/sessions/2026-08-11/BANKNIFTY_underlying.json`: DELETE
- `data/raw/upstox/sessions/2026-08-11/NIFTY_underlying.json`: DELETE
- `data/raw/upstox/sessions/2026-08-12/BANKNIFTY_underlying.json`: DELETE
- `data/raw/upstox/sessions/2026-08-12/NIFTY_underlying.json`: DELETE
- `data/raw/upstox/sessions/2026-08-13/BANKNIFTY_underlying.json`: DELETE
- `data/raw/upstox/sessions/2026-08-13/NIFTY_underlying.json`: DELETE
- `data/raw/upstox/sessions/2026-08-14/BANKNIFTY_underlying.json`: DELETE
- `data/raw/upstox/sessions/2026-08-14/NIFTY_underlying.json`: DELETE
- `data/raw/upstox/sessions/2026-08-17/BANKNIFTY_underlying.json`: DELETE
- `data/raw/upstox/sessions/2026-08-17/NIFTY_underlying.json`: DELETE
- `data/raw/upstox/sessions/2026-08-18/BANKNIFTY_underlying.json`: DELETE
- `data/raw/upstox/sessions/2026-08-18/NIFTY_underlying.json`: DELETE
- `data/raw/upstox/sessions/2026-08-19/BANKNIFTY_underlying.json`: DELETE
- `data/raw/upstox/sessions/2026-08-19/NIFTY_underlying.json`: DELETE
- `data/raw/upstox/sessions/2026-08-20/BANKNIFTY_underlying.json`: DELETE
- `data/raw/upstox/sessions/2026-08-20/NIFTY_underlying.json`: DELETE
- `data/raw/upstox/sessions/2026-08-21/BANKNIFTY_underlying.json`: DELETE
- `data/raw/upstox/sessions/2026-08-21/NIFTY_underlying.json`: DELETE
- `data/raw/upstox/sessions/2026-08-24/BANKNIFTY_underlying.json`: DELETE
- `data/raw/upstox/sessions/2026-08-24/NIFTY_underlying.json`: DELETE
- `data/raw/upstox/sessions/2026-08-25/BANKNIFTY_opt_NSE_FO_69824.json`: DELETE
- `data/raw/upstox/sessions/2026-08-25/BANKNIFTY_opt_NSE_FO_69825.json`: DELETE
- `data/raw/upstox/sessions/2026-08-25/BANKNIFTY_opt_NSE_FO_69826.json`: DELETE
- `data/raw/upstox/sessions/2026-08-25/BANKNIFTY_opt_NSE_FO_69827.json`: DELETE
- `data/raw/upstox/sessions/2026-08-25/BANKNIFTY_opt_NSE_FO_69828.json`: DELETE
- `data/raw/upstox/sessions/2026-08-25/BANKNIFTY_opt_NSE_FO_69829.json`: DELETE
- `data/raw/upstox/sessions/2026-08-25/BANKNIFTY_opt_NSE_FO_69832.json`: DELETE
- `data/raw/upstox/sessions/2026-08-25/BANKNIFTY_opt_NSE_FO_69833.json`: DELETE
- `data/raw/upstox/sessions/2026-08-25/BANKNIFTY_opt_NSE_FO_69838.json`: DELETE
- `data/raw/upstox/sessions/2026-08-25/BANKNIFTY_opt_NSE_FO_69839.json`: DELETE
- `data/raw/upstox/sessions/2026-08-25/BANKNIFTY_underlying.json`: DELETE
- `data/raw/upstox/sessions/2026-08-25/NIFTY_opt_NSE_FO_46989.json`: DELETE
- `data/raw/upstox/sessions/2026-08-25/NIFTY_opt_NSE_FO_46990.json`: DELETE
- `data/raw/upstox/sessions/2026-08-25/NIFTY_opt_NSE_FO_46991.json`: DELETE
- `data/raw/upstox/sessions/2026-08-25/NIFTY_opt_NSE_FO_46992.json`: DELETE
- `data/raw/upstox/sessions/2026-08-25/NIFTY_opt_NSE_FO_46993.json`: DELETE
- `data/raw/upstox/sessions/2026-08-25/NIFTY_opt_NSE_FO_46994.json`: DELETE
- `data/raw/upstox/sessions/2026-08-25/NIFTY_opt_NSE_FO_46995.json`: DELETE
- `data/raw/upstox/sessions/2026-08-25/NIFTY_opt_NSE_FO_46996.json`: DELETE
- `data/raw/upstox/sessions/2026-08-25/NIFTY_opt_NSE_FO_46997.json`: DELETE
- `data/raw/upstox/sessions/2026-08-25/NIFTY_opt_NSE_FO_46998.json`: DELETE
- `data/raw/upstox/sessions/2026-08-25/NIFTY_underlying.json`: DELETE
- `data/raw/upstox/sessions/2026-08-25/session_manifest.json`: DELETE
- `data/raw/upstox/sessions/2026-08-26/BANKNIFTY_underlying.json`: DELETE
- `data/raw/upstox/sessions/2026-08-26/NIFTY_underlying.json`: DELETE
- `data/raw/upstox/sessions/2026-08-27/BANKNIFTY_underlying.json`: DELETE
- `data/raw/upstox/sessions/2026-08-27/NIFTY_underlying.json`: DELETE
- `data/raw/upstox/sessions/2026-08-28/BANKNIFTY_underlying.json`: DELETE
- `data/raw/upstox/sessions/2026-08-28/NIFTY_underlying.json`: DELETE
- `data/raw/upstox/upstox_bod_instruments_master.csv`: DELETE
- `data/replays/challenger_tournament_v1/tournament_summary.json`: DELETE
- `data/replays/champion_replacement_tournament_v2/tournament_scorecard_v2.json`: DELETE
- `data/replays/micro_edge_discovery_v2/micro_edge_discovery_summary.json`: DELETE
- `data/replays/walk_forward_2026-08-04_to_2026-08-25/walk_forward_summary.json`: DELETE
- `data/runtime/pre_market_acceptance.json`: DELETE
- `dist/.gitignore`: DELETE
- `dist/ats-0.0.0-py3-none-any.whl`: DELETE
- `dist/ats-0.0.0.tar.gz`: DELETE
- `reports/ATS_BROKER_CAPABILITY_MATRIX.csv`: DELETE
- `reports/ATS_BROKER_CONNECTION_GUIDE.md`: DELETE
- `reports/ATS_BROKER_CONNECTOR_ARCHITECTURE.md`: DELETE
- `reports/ATS_BROKER_SECURITY_REPORT.md`: DELETE
- `reports/ATS_LIVE_MARKET_PAPER_REPORT.md`: DELETE
- `reports/ATS_LIVE_PAPER_BROWSER_ACCEPTANCE.md`: DELETE
- `reports/ATS_LIVE_PAPER_WIRING_MAP.md`: DELETE
- `reports/ATS_PLATFORM_FULL_REGRESSION_REPORT.md`: DELETE
- `reports/ATS_PRODUCT_READINESS_MANIFEST.json`: DELETE
- `reports/ATS_SETTINGS_CONTROL_PLANE_REPORT.md`: DELETE
- `reports/ATS_SETTINGS_SCHEMA.json`: DELETE
- `reports/ATS_STRATEGY_HISTORY_MIGRATION_REPORT.md`: DELETE
- `reports/ATS_USER_STARTUP_GUIDE.md`: DELETE
- `reports/operator-runtime/backend.err.log`: DELETE
- `reports/operator-runtime/backend.log`: DELETE
- `reports/operator-runtime/frontend.err.log`: DELETE
- `reports/operator-runtime/frontend.log`: DELETE
- `reports/operator-runtime/processes.json`: DELETE
- `scripts/baseline_research_nifty.py`: DELETE
- `scripts/comprehensive_ats_acceptance.py`: DELETE
- `scripts/cost_stress_check.py`: DELETE
- `scripts/evolve_families.py`: DELETE
- `scripts/probe_diverse_families.py`: DELETE
- `scripts/run_paper_sessions.py`: DELETE
- `scripts/start_ats_a2_live_paper.ps1`: DELETE
- `scripts/test_chart360_atomic_audit.py`: DELETE
- `scripts/test_dynamic_datasets_and_chart360.py`: DELETE
- `scripts/test_laya_integration.py`: DELETE
- `scripts/test_lc1_live_streaming_acceptance.py`: DELETE
- `scripts/test_ui_interactions.py`: DELETE
- `scripts/validate_strategies.py`: DELETE
- `tests/contract/market/derivatives/__pycache__/__init__.cpython-311.pyc`: DELETE
- `tests/contract/market/derivatives/__pycache__/test_contract_master_schema.cpython-311-pytest-8.4.2.pyc`: DELETE
- `tests/contract/market/derivatives/__pycache__/test_option_chain_contract.cpython-311-pytest-8.4.2.pyc`: DELETE
- `tests/contract/market/derivatives/acquisition/__pycache__/__init__.cpython-311.pyc`: DELETE
- `tests/contract/market/derivatives/acquisition/__pycache__/test_d03_read_only_contract.cpython-311-pytest-8.4.2.pyc`: DELETE
- `tests/contract/market/derivatives/acquisition/test_d03_read_only_contract.py`: DELETE
- `tests/contract/market/derivatives/normalization/__pycache__/__init__.cpython-311.pyc`: DELETE
- `tests/contract/market/derivatives/normalization/__pycache__/test_d02_contract.cpython-311-pytest-8.4.2.pyc`: DELETE
- `tests/contract/market/derivatives/normalization/test_d02_contract.py`: DELETE
- `tests/contract/market/derivatives/providers/__pycache__/__init__.cpython-311.pyc`: DELETE
- `tests/contract/market/derivatives/providers/__pycache__/test_provider_boundary.cpython-311-pytest-8.4.2.pyc`: DELETE
- `tests/contract/market/derivatives/providers/test_provider_boundary.py`: DELETE
- `tests/contract/market/derivatives/test_contract_master_schema.py`: DELETE
- `tests/contract/market/derivatives/test_option_chain_contract.py`: DELETE
- `tests/integration/market/derivatives/__pycache__/__init__.cpython-311.pyc`: DELETE
- `tests/integration/market/derivatives/__pycache__/test_contract_master_fixture.cpython-311-pytest-8.4.2.pyc`: DELETE
- `tests/integration/market/derivatives/__pycache__/test_end_to_end_readiness.cpython-311-pytest-8.4.2.pyc`: DELETE
- `tests/integration/market/derivatives/__pycache__/test_option_chain_pipeline.cpython-311-pytest-8.4.2.pyc`: DELETE
- `tests/integration/market/derivatives/active_window/__pycache__/__init__.cpython-311.pyc`: DELETE
- `tests/integration/market/derivatives/active_window/__pycache__/test_d02_d04_integration.cpython-311-pytest-8.4.2.pyc`: DELETE
- `tests/integration/market/derivatives/active_window/test_d02_d04_integration.py`: DELETE
- `tests/integration/market/derivatives/fixtures/nse_index_derivatives_20260824.csv`: DELETE
- `tests/integration/market/derivatives/test_contract_master_fixture.py`: DELETE
- `tests/integration/market/derivatives/test_end_to_end_readiness.py`: DELETE
- `tests/integration/market/derivatives/test_option_chain_pipeline.py`: DELETE
- `tests/property/market/derivatives/__pycache__/__init__.cpython-311.pyc`: DELETE
- `tests/property/market/derivatives/active_window/__pycache__/__init__.cpython-311.pyc`: DELETE
- `tests/property/market/derivatives/active_window/__pycache__/test_d04_window_properties.cpython-311-pytest-8.4.2.pyc`: DELETE
- `tests/property/market/derivatives/active_window/test_d04_window_properties.py`: DELETE
- `tests/property/market/derivatives/contract_master/__pycache__/__init__.cpython-311.pyc`: DELETE
- `tests/property/market/derivatives/contract_master/__pycache__/test_contract_master_properties.cpython-311-pytest-8.4.2.pyc`: DELETE
- `tests/property/market/derivatives/contract_master/test_contract_master_properties.py`: DELETE
- `tests/property/market/derivatives/normalization/__pycache__/__init__.cpython-311.pyc`: DELETE
- `tests/property/market/derivatives/normalization/__pycache__/test_canonical_stability.cpython-311-pytest-8.4.2.pyc`: DELETE
- `tests/property/market/derivatives/normalization/test_canonical_stability.py`: DELETE
- `tests/property/market/derivatives/option_chain/__pycache__/__init__.cpython-311.pyc`: DELETE
- `tests/property/market/derivatives/option_chain/__pycache__/test_option_chain_properties.cpython-311-pytest-8.4.2.pyc`: DELETE
- `tests/property/market/derivatives/option_chain/test_option_chain_properties.py`: DELETE
- `tests/property/market/derivatives/replay_data/__pycache__/__init__.cpython-311.pyc`: DELETE
- `tests/property/market/derivatives/replay_data/__pycache__/test_d03_temporal_properties.cpython-311-pytest-8.4.2.pyc`: DELETE
- `tests/property/market/derivatives/replay_data/test_d03_temporal_properties.py`: DELETE
- `tests/unit/market/data_acquisition/__pycache__/__init__.cpython-311.pyc`: DELETE
- `tests/unit/market/data_acquisition/__pycache__/test_real_session_ingestion.cpython-311-pytest-8.4.2.pyc`: DELETE
- `tests/unit/market/data_acquisition/test_real_session_ingestion.py`: DELETE
- `tests/unit/market/derivatives/__init__.py`: DELETE
- `tests/unit/market/derivatives/__pycache__/__init__.cpython-311.pyc`: DELETE
- `tests/unit/market/derivatives/acquisition/__pycache__/__init__.cpython-311.pyc`: DELETE
- `tests/unit/market/derivatives/acquisition/__pycache__/test_client.cpython-311-pytest-8.4.2.pyc`: DELETE
- `tests/unit/market/derivatives/acquisition/__pycache__/test_parsers.cpython-311-pytest-8.4.2.pyc`: DELETE
- `tests/unit/market/derivatives/acquisition/__pycache__/test_plan.cpython-311-pytest-8.4.2.pyc`: DELETE
- `tests/unit/market/derivatives/acquisition/__pycache__/test_redaction.cpython-311-pytest-8.4.2.pyc`: DELETE
- `tests/unit/market/derivatives/acquisition/__pycache__/test_secrets.cpython-311-pytest-8.4.2.pyc`: DELETE
- `tests/unit/market/derivatives/acquisition/test_client.py`: DELETE
- `tests/unit/market/derivatives/acquisition/test_parsers.py`: DELETE
- `tests/unit/market/derivatives/acquisition/test_plan.py`: DELETE
- `tests/unit/market/derivatives/acquisition/test_redaction.py`: DELETE
- `tests/unit/market/derivatives/acquisition/test_secrets.py`: DELETE
- `tests/unit/market/derivatives/active_window/__init__.py`: DELETE
- `tests/unit/market/derivatives/active_window/__pycache__/__init__.cpython-311.pyc`: DELETE
- `tests/unit/market/derivatives/active_window/__pycache__/test_cache.cpython-311-pytest-8.4.2.pyc`: DELETE
- `tests/unit/market/derivatives/active_window/__pycache__/test_engine.cpython-311-pytest-8.4.2.pyc`: DELETE
- `tests/unit/market/derivatives/active_window/test_cache.py`: DELETE
- `tests/unit/market/derivatives/active_window/test_engine.py`: DELETE
- `tests/unit/market/derivatives/artifacts/__pycache__/__init__.cpython-311.pyc`: DELETE
- `tests/unit/market/derivatives/artifacts/__pycache__/test_artifact_provenance.cpython-311-pytest-8.4.2.pyc`: DELETE
- `tests/unit/market/derivatives/artifacts/__pycache__/test_store.cpython-311-pytest-8.4.2.pyc`: DELETE
- `tests/unit/market/derivatives/artifacts/test_artifact_provenance.py`: DELETE
- `tests/unit/market/derivatives/artifacts/test_store.py`: DELETE
- `tests/unit/market/derivatives/contract_master/__init__.py`: DELETE
- `tests/unit/market/derivatives/contract_master/__pycache__/__init__.cpython-311.pyc`: DELETE
- `tests/unit/market/derivatives/contract_master/__pycache__/expiry_helpers.cpython-311.pyc`: DELETE
- `tests/unit/market/derivatives/contract_master/__pycache__/helpers.cpython-311.pyc`: DELETE
- `tests/unit/market/derivatives/contract_master/__pycache__/test_expiry_engine.cpython-311-pytest-8.4.2.pyc`: DELETE
- `tests/unit/market/derivatives/contract_master/__pycache__/test_normalization.cpython-311-pytest-8.4.2.pyc`: DELETE
- `tests/unit/market/derivatives/contract_master/__pycache__/test_registry.cpython-311-pytest-8.4.2.pyc`: DELETE
- `tests/unit/market/derivatives/contract_master/expiry_helpers.py`: DELETE
- `tests/unit/market/derivatives/contract_master/helpers.py`: DELETE
- `tests/unit/market/derivatives/contract_master/test_expiry_engine.py`: DELETE
- `tests/unit/market/derivatives/contract_master/test_normalization.py`: DELETE
- `tests/unit/market/derivatives/contract_master/test_registry.py`: DELETE
- `tests/unit/market/derivatives/normalization/__pycache__/__init__.cpython-311.pyc`: DELETE
- `tests/unit/market/derivatives/normalization/__pycache__/test_normalizer.cpython-311-pytest-8.4.2.pyc`: DELETE
- `tests/unit/market/derivatives/normalization/test_normalizer.py`: DELETE
- `tests/unit/market/derivatives/option_chain/__init__.py`: DELETE
- `tests/unit/market/derivatives/option_chain/__pycache__/__init__.cpython-311.pyc`: DELETE
- `tests/unit/market/derivatives/option_chain/__pycache__/helpers.cpython-311.pyc`: DELETE
- `tests/unit/market/derivatives/option_chain/__pycache__/test_builder.cpython-311-pytest-8.4.2.pyc`: DELETE
- `tests/unit/market/derivatives/option_chain/__pycache__/test_features.cpython-311-pytest-8.4.2.pyc`: DELETE
- `tests/unit/market/derivatives/option_chain/__pycache__/test_greeks_calculator.cpython-311-pytest-8.4.2.pyc`: DELETE
- `tests/unit/market/derivatives/option_chain/helpers.py`: DELETE
- `tests/unit/market/derivatives/option_chain/test_builder.py`: DELETE
- `tests/unit/market/derivatives/option_chain/test_features.py`: DELETE
- `tests/unit/market/derivatives/option_chain/test_greeks_calculator.py`: DELETE
- `tests/unit/market/derivatives/providers/__pycache__/__init__.cpython-311.pyc`: DELETE
- `tests/unit/market/derivatives/providers/__pycache__/test_provenance.cpython-311-pytest-8.4.2.pyc`: DELETE
- `tests/unit/market/derivatives/providers/test_provenance.py`: DELETE
- `tests/unit/market/derivatives/replay_data/__pycache__/__init__.cpython-311.pyc`: DELETE
- `tests/unit/market/derivatives/replay_data/__pycache__/test_builder.cpython-311-pytest-8.4.2.pyc`: DELETE
- `tests/unit/market/derivatives/replay_data/__pycache__/test_resampler.cpython-311-pytest-8.4.2.pyc`: DELETE
- `tests/unit/market/derivatives/replay_data/test_builder.py`: DELETE
- `tests/unit/market/derivatives/replay_data/test_resampler.py`: DELETE
- `tests/unit/market/derivatives/strike_window/__init__.py`: DELETE
- `tests/unit/market/derivatives/strike_window/__pycache__/__init__.cpython-311.pyc`: DELETE
- `tests/unit/market/derivatives/strike_window/__pycache__/helpers.cpython-311.pyc`: DELETE
- `tests/unit/market/derivatives/strike_window/__pycache__/test_strike_window.cpython-311-pytest-8.4.2.pyc`: DELETE
- `tests/unit/market/derivatives/strike_window/helpers.py`: DELETE
- `tests/unit/market/derivatives/strike_window/test_strike_window.py`: DELETE
- `tests/unit/market/feeds/upstox_v3/__init__.py`: DELETE
- `tests/unit/market/feeds/upstox_v3/__pycache__/__init__.cpython-311.pyc`: DELETE
- `tests/unit/market/feeds/upstox_v3/__pycache__/helpers.cpython-311.pyc`: DELETE
- `tests/unit/market/feeds/upstox_v3/__pycache__/test_adapter.cpython-311-pytest-8.4.2.pyc`: DELETE
- `tests/unit/market/feeds/upstox_v3/__pycache__/test_codec.cpython-311-pytest-8.4.2.pyc`: DELETE
- `tests/unit/market/feeds/upstox_v3/__pycache__/test_frames.cpython-311-pytest-8.4.2.pyc`: DELETE
- `tests/unit/market/feeds/upstox_v3/__pycache__/test_freshness.cpython-311-pytest-8.4.2.pyc`: DELETE
- `tests/unit/market/feeds/upstox_v3/__pycache__/test_protobuf_codec.cpython-311-pytest-8.4.2.pyc`: DELETE
- `tests/unit/market/feeds/upstox_v3/__pycache__/test_subscription.cpython-311-pytest-8.4.2.pyc`: DELETE
- `tests/unit/market/feeds/upstox_v3/__pycache__/test_transport.cpython-311-pytest-8.4.2.pyc`: DELETE
- `tests/unit/market/feeds/upstox_v3/helpers.py`: DELETE
- `tests/unit/market/feeds/upstox_v3/test_adapter.py`: DELETE
- `tests/unit/market/feeds/upstox_v3/test_codec.py`: DELETE
- `tests/unit/market/feeds/upstox_v3/test_frames.py`: DELETE
- `tests/unit/market/feeds/upstox_v3/test_freshness.py`: DELETE
- `tests/unit/market/feeds/upstox_v3/test_protobuf_codec.py`: DELETE
- `tests/unit/market/feeds/upstox_v3/test_subscription.py`: DELETE
- `tests/unit/market/feeds/upstox_v3/test_transport.py`: DELETE
- `tests/unit/market/providers/upstox/__pycache__/__init__.cpython-311.pyc`: DELETE
- `tests/unit/market/providers/upstox/__pycache__/test_capabilities.cpython-311-pytest-8.4.2.pyc`: DELETE
- `tests/unit/market/providers/upstox/test_capabilities.py`: DELETE
- `verify_all_features.py`: DELETE

## Reviewed deletion decisions before purge

Recovery ZIP verified against all 1,012 original file hashes. The following reviewed paths are DELETE. Generic strategy source is relocated before persona removal. Core authorization algorithms are retained.

- `backend/src/data/market_journal/journal_upstox_20260924_07.jsonl`: DELETE
- `backend/src/data/market_journal/journal_upstox_20260924_08.jsonl`: DELETE
- `data/agents/agents_config.json`: DELETE
- `data/agents/roster.json`: DELETE
- `data/agents/upstox_live_trades_ledger.json`: DELETE
- `data/datasets/datasets_manifest.json`: DELETE
- `data/forward_validation/evidence_ledger.jsonl`: DELETE
- `data/historical/banknifty_options_a2_replay_v1/manifest.json`: DELETE
- `data/historical/banknifty_options_a2_replay_v1/observations.jsonl`: DELETE
- `data/historical/banknifty_options_a2_replay_v1/policy.json`: DELETE
- `data/historical/banknifty_options_a2_replay_v1/records.sha256`: DELETE
- `data/historical/calibration_store_v1.json`: DELETE
- `data/historical/calibration_stores/A1_calibration_store.json`: DELETE
- `data/historical/calibration_stores/A2_calibration_store.json`: DELETE
- `data/historical/calibration_stores/A3_calibration_store.json`: DELETE
- `data/historical/calibration_stores/A4_calibration_store.json`: DELETE
- `data/historical/calibration_stores/C0_calibration_store.json`: DELETE
- `data/historical/calibration_stores/C1_calibration_store.json`: DELETE
- `data/historical/calibration_stores/C2_calibration_store.json`: DELETE
- `data/historical/calibration_stores/C3_calibration_store.json`: DELETE
- `data/historical/calibration_stores/C4_calibration_store.json`: DELETE
- `data/historical/calibration_stores/C5_calibration_store.json`: DELETE
- `data/historical/nifty_options_a2_replay_v1/manifest.json`: DELETE
- `data/historical/nifty_options_a2_replay_v1/observations.jsonl`: DELETE
- `data/historical/nifty_options_a2_replay_v1/policy.json`: DELETE
- `data/historical/nifty_options_a2_replay_v1/records.sha256`: DELETE
- `data/market_journal/journal_upstox_20260923_18.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260924_04.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260924_05.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260924_06.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260924_07.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260924_08.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260924_16.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260924_17.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260924_18.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260924_19.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260924_20.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260924_21.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260924_22.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260924_23.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260925_03.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260925_04.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260925_05.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260925_06.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260925_07.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260925_08.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260925_09.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260925_10.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260925_11.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260925_12.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260925_13.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260925_14.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260925_15.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260925_16.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260925_17.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260925_22.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260926_06.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260926_16.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260927_02.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260927_09.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260927_10.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260927_14.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260927_16.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260927_17.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260927_18.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260927_19.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260928_08.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260928_09.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260928_10.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260928_11.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260928_12.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260928_13.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260928_14.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260928_15.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260928_16.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260928_17.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260929_08.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260929_09.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260929_10.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260930_05.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260930_06.jsonl`: DELETE
- `data/market_journal/journal_upstox_20260930_07.jsonl`: DELETE
- `data/market_journal/journal_upstox_20261001_04.jsonl`: DELETE
- `data/market_journal/journal_upstox_20261001_05.jsonl`: DELETE
- `data/market_journal/journal_upstox_20261001_06.jsonl`: DELETE
- `data/market_journal/journal_upstox_20261001_07.jsonl`: DELETE
- `data/market_journal/journal_upstox_20261001_08.jsonl`: DELETE
- `data/market_journal/journal_upstox_20261001_09.jsonl`: DELETE
- `data/market_journal/journal_upstox_20261001_10.jsonl`: DELETE
- `data/market_journal/journal_upstox_20261003_10.jsonl`: DELETE
- `data/market_journal/journal_upstox_20261003_11.jsonl`: DELETE
- `data/market_journal/journal_upstox_20261004_11.jsonl`: DELETE
- `data/market_journal/journal_upstox_20261005_12.jsonl`: DELETE
- `data/market_journal/journal_upstox_20261005_13.jsonl`: DELETE
- `data/market_journal/journal_upstox_20261005_21.jsonl`: DELETE
- `data/market_journal/journal_upstox_20261006_10.jsonl`: DELETE
- `data/raw/upstox/banknifty_option_chain.json`: DELETE
- `data/raw/upstox/nifty_option_chain.json`: DELETE
- `data/raw/upstox/sessions/2026-08-04/BANKNIFTY_underlying.json`: DELETE
- `data/raw/upstox/sessions/2026-08-04/NIFTY_underlying.json`: DELETE
- `data/raw/upstox/sessions/2026-08-05/BANKNIFTY_underlying.json`: DELETE
- `data/raw/upstox/sessions/2026-08-05/NIFTY_underlying.json`: DELETE
- `data/raw/upstox/sessions/2026-08-06/BANKNIFTY_underlying.json`: DELETE
- `data/raw/upstox/sessions/2026-08-06/NIFTY_underlying.json`: DELETE
- `data/raw/upstox/sessions/2026-08-07/BANKNIFTY_underlying.json`: DELETE
- `data/raw/upstox/sessions/2026-08-07/NIFTY_underlying.json`: DELETE
- `data/raw/upstox/sessions/2026-08-10/BANKNIFTY_underlying.json`: DELETE
- `data/raw/upstox/sessions/2026-08-10/NIFTY_underlying.json`: DELETE
- `data/raw/upstox/sessions/2026-08-11/BANKNIFTY_underlying.json`: DELETE
- `data/raw/upstox/sessions/2026-08-11/NIFTY_underlying.json`: DELETE
- `data/raw/upstox/sessions/2026-08-12/BANKNIFTY_underlying.json`: DELETE
- `data/raw/upstox/sessions/2026-08-12/NIFTY_underlying.json`: DELETE
- `data/raw/upstox/sessions/2026-08-13/BANKNIFTY_underlying.json`: DELETE
- `data/raw/upstox/sessions/2026-08-13/NIFTY_underlying.json`: DELETE
- `data/raw/upstox/sessions/2026-08-14/BANKNIFTY_underlying.json`: DELETE
- `data/raw/upstox/sessions/2026-08-14/NIFTY_underlying.json`: DELETE
- `data/raw/upstox/sessions/2026-08-17/BANKNIFTY_underlying.json`: DELETE
- `data/raw/upstox/sessions/2026-08-17/NIFTY_underlying.json`: DELETE
- `data/raw/upstox/sessions/2026-08-18/BANKNIFTY_underlying.json`: DELETE
- `data/raw/upstox/sessions/2026-08-18/NIFTY_underlying.json`: DELETE
- `data/raw/upstox/sessions/2026-08-19/BANKNIFTY_underlying.json`: DELETE
- `data/raw/upstox/sessions/2026-08-19/NIFTY_underlying.json`: DELETE
- `data/raw/upstox/sessions/2026-08-20/BANKNIFTY_underlying.json`: DELETE
- `data/raw/upstox/sessions/2026-08-20/NIFTY_underlying.json`: DELETE
- `data/raw/upstox/sessions/2026-08-21/BANKNIFTY_underlying.json`: DELETE
- `data/raw/upstox/sessions/2026-08-21/NIFTY_underlying.json`: DELETE
- `data/raw/upstox/sessions/2026-08-24/BANKNIFTY_underlying.json`: DELETE
- `data/raw/upstox/sessions/2026-08-24/NIFTY_underlying.json`: DELETE
- `data/raw/upstox/sessions/2026-08-25/BANKNIFTY_opt_NSE_FO_69824.json`: DELETE
- `data/raw/upstox/sessions/2026-08-25/BANKNIFTY_opt_NSE_FO_69825.json`: DELETE
- `data/raw/upstox/sessions/2026-08-25/BANKNIFTY_opt_NSE_FO_69826.json`: DELETE
- `data/raw/upstox/sessions/2026-08-25/BANKNIFTY_opt_NSE_FO_69827.json`: DELETE
- `data/raw/upstox/sessions/2026-08-25/BANKNIFTY_opt_NSE_FO_69828.json`: DELETE
- `data/raw/upstox/sessions/2026-08-25/BANKNIFTY_opt_NSE_FO_69829.json`: DELETE
- `data/raw/upstox/sessions/2026-08-25/BANKNIFTY_opt_NSE_FO_69832.json`: DELETE
- `data/raw/upstox/sessions/2026-08-25/BANKNIFTY_opt_NSE_FO_69833.json`: DELETE
- `data/raw/upstox/sessions/2026-08-25/BANKNIFTY_opt_NSE_FO_69838.json`: DELETE
- `data/raw/upstox/sessions/2026-08-25/BANKNIFTY_opt_NSE_FO_69839.json`: DELETE
- `data/raw/upstox/sessions/2026-08-25/BANKNIFTY_underlying.json`: DELETE
- `data/raw/upstox/sessions/2026-08-25/NIFTY_opt_NSE_FO_46989.json`: DELETE
- `data/raw/upstox/sessions/2026-08-25/NIFTY_opt_NSE_FO_46990.json`: DELETE
- `data/raw/upstox/sessions/2026-08-25/NIFTY_opt_NSE_FO_46991.json`: DELETE
- `data/raw/upstox/sessions/2026-08-25/NIFTY_opt_NSE_FO_46992.json`: DELETE
- `data/raw/upstox/sessions/2026-08-25/NIFTY_opt_NSE_FO_46993.json`: DELETE
- `data/raw/upstox/sessions/2026-08-25/NIFTY_opt_NSE_FO_46994.json`: DELETE
- `data/raw/upstox/sessions/2026-08-25/NIFTY_opt_NSE_FO_46995.json`: DELETE
- `data/raw/upstox/sessions/2026-08-25/NIFTY_opt_NSE_FO_46996.json`: DELETE
- `data/raw/upstox/sessions/2026-08-25/NIFTY_opt_NSE_FO_46997.json`: DELETE
- `data/raw/upstox/sessions/2026-08-25/NIFTY_opt_NSE_FO_46998.json`: DELETE
- `data/raw/upstox/sessions/2026-08-25/NIFTY_underlying.json`: DELETE
- `data/raw/upstox/sessions/2026-08-25/session_manifest.json`: DELETE
- `data/raw/upstox/sessions/2026-08-26/BANKNIFTY_underlying.json`: DELETE
- `data/raw/upstox/sessions/2026-08-26/NIFTY_underlying.json`: DELETE
- `data/raw/upstox/sessions/2026-08-27/BANKNIFTY_underlying.json`: DELETE
- `data/raw/upstox/sessions/2026-08-27/NIFTY_underlying.json`: DELETE
- `data/raw/upstox/sessions/2026-08-28/BANKNIFTY_underlying.json`: DELETE
- `data/raw/upstox/sessions/2026-08-28/NIFTY_underlying.json`: DELETE
- `data/raw/upstox/upstox_bod_instruments_master.csv`: DELETE
- `data/replays/challenger_tournament_v1/tournament_summary.json`: DELETE
- `data/replays/champion_replacement_tournament_v2/tournament_scorecard_v2.json`: DELETE
- `data/replays/micro_edge_discovery_v2/micro_edge_discovery_summary.json`: DELETE
- `data/replays/walk_forward_2026-08-04_to_2026-08-25/walk_forward_summary.json`: DELETE
- `data/runtime/pre_market_acceptance.json`: DELETE
- `dist/.gitignore`: DELETE
- `dist/ats-0.0.0-py3-none-any.whl`: DELETE
- `dist/ats-0.0.0.tar.gz`: DELETE
- `reports/ATS_BROKER_CAPABILITY_MATRIX.csv`: DELETE
- `reports/ATS_BROKER_CONNECTION_GUIDE.md`: DELETE
- `reports/ATS_BROKER_CONNECTOR_ARCHITECTURE.md`: DELETE
- `reports/ATS_BROKER_SECURITY_REPORT.md`: DELETE
- `reports/ATS_LIVE_MARKET_PAPER_REPORT.md`: DELETE
- `reports/ATS_LIVE_PAPER_BROWSER_ACCEPTANCE.md`: DELETE
- `reports/ATS_LIVE_PAPER_WIRING_MAP.md`: DELETE
- `reports/ATS_PLATFORM_FULL_REGRESSION_REPORT.md`: DELETE
- `reports/ATS_PRODUCT_READINESS_MANIFEST.json`: DELETE
- `reports/ATS_SETTINGS_CONTROL_PLANE_REPORT.md`: DELETE
- `reports/ATS_SETTINGS_SCHEMA.json`: DELETE
- `reports/ATS_STRATEGY_HISTORY_MIGRATION_REPORT.md`: DELETE
- `reports/ATS_USER_STARTUP_GUIDE.md`: DELETE
- `reports/operator-runtime/backend.err.log`: DELETE
- `reports/operator-runtime/backend.log`: DELETE
- `reports/operator-runtime/frontend.err.log`: DELETE
- `reports/operator-runtime/frontend.log`: DELETE
- `reports/operator-runtime/processes.json`: DELETE
- `scripts/baseline_research_nifty.py`: DELETE
- `scripts/comprehensive_ats_acceptance.py`: DELETE
- `scripts/cost_stress_check.py`: DELETE
- `scripts/evolve_families.py`: DELETE
- `scripts/probe_diverse_families.py`: DELETE
- `scripts/run_paper_sessions.py`: DELETE
- `scripts/start_ats_a2_live_paper.ps1`: DELETE
- `scripts/test_chart360_atomic_audit.py`: DELETE
- `scripts/test_dynamic_datasets_and_chart360.py`: DELETE
- `scripts/test_laya_integration.py`: DELETE
- `scripts/test_lc1_live_streaming_acceptance.py`: DELETE
- `scripts/test_ui_interactions.py`: DELETE
- `scripts/validate_strategies.py`: DELETE
- `tests/contract/market/derivatives/__pycache__/__init__.cpython-311.pyc`: DELETE
- `tests/contract/market/derivatives/__pycache__/test_contract_master_schema.cpython-311-pytest-8.4.2.pyc`: DELETE
- `tests/contract/market/derivatives/__pycache__/test_option_chain_contract.cpython-311-pytest-8.4.2.pyc`: DELETE
- `tests/contract/market/derivatives/acquisition/__pycache__/__init__.cpython-311.pyc`: DELETE
- `tests/contract/market/derivatives/acquisition/__pycache__/test_d03_read_only_contract.cpython-311-pytest-8.4.2.pyc`: DELETE
- `tests/contract/market/derivatives/acquisition/test_d03_read_only_contract.py`: DELETE
- `tests/contract/market/derivatives/normalization/__pycache__/__init__.cpython-311.pyc`: DELETE
- `tests/contract/market/derivatives/normalization/__pycache__/test_d02_contract.cpython-311-pytest-8.4.2.pyc`: DELETE
- `tests/contract/market/derivatives/normalization/test_d02_contract.py`: DELETE
- `tests/contract/market/derivatives/providers/__pycache__/__init__.cpython-311.pyc`: DELETE
- `tests/contract/market/derivatives/providers/__pycache__/test_provider_boundary.cpython-311-pytest-8.4.2.pyc`: DELETE
- `tests/contract/market/derivatives/providers/test_provider_boundary.py`: DELETE
- `tests/contract/market/derivatives/test_contract_master_schema.py`: DELETE
- `tests/contract/market/derivatives/test_option_chain_contract.py`: DELETE
- `tests/integration/market/derivatives/__pycache__/__init__.cpython-311.pyc`: DELETE
- `tests/integration/market/derivatives/__pycache__/test_contract_master_fixture.cpython-311-pytest-8.4.2.pyc`: DELETE
- `tests/integration/market/derivatives/__pycache__/test_end_to_end_readiness.cpython-311-pytest-8.4.2.pyc`: DELETE
- `tests/integration/market/derivatives/__pycache__/test_option_chain_pipeline.cpython-311-pytest-8.4.2.pyc`: DELETE
- `tests/integration/market/derivatives/active_window/__pycache__/__init__.cpython-311.pyc`: DELETE
- `tests/integration/market/derivatives/active_window/__pycache__/test_d02_d04_integration.cpython-311-pytest-8.4.2.pyc`: DELETE
- `tests/integration/market/derivatives/active_window/test_d02_d04_integration.py`: DELETE
- `tests/integration/market/derivatives/fixtures/nse_index_derivatives_20260824.csv`: DELETE
- `tests/integration/market/derivatives/test_contract_master_fixture.py`: DELETE
- `tests/integration/market/derivatives/test_end_to_end_readiness.py`: DELETE
- `tests/integration/market/derivatives/test_option_chain_pipeline.py`: DELETE
- `tests/property/market/derivatives/__pycache__/__init__.cpython-311.pyc`: DELETE
- `tests/property/market/derivatives/active_window/__pycache__/__init__.cpython-311.pyc`: DELETE
- `tests/property/market/derivatives/active_window/__pycache__/test_d04_window_properties.cpython-311-pytest-8.4.2.pyc`: DELETE
- `tests/property/market/derivatives/active_window/test_d04_window_properties.py`: DELETE
- `tests/property/market/derivatives/contract_master/__pycache__/__init__.cpython-311.pyc`: DELETE
- `tests/property/market/derivatives/contract_master/__pycache__/test_contract_master_properties.cpython-311-pytest-8.4.2.pyc`: DELETE
- `tests/property/market/derivatives/contract_master/test_contract_master_properties.py`: DELETE
- `tests/property/market/derivatives/normalization/__pycache__/__init__.cpython-311.pyc`: DELETE
- `tests/property/market/derivatives/normalization/__pycache__/test_canonical_stability.cpython-311-pytest-8.4.2.pyc`: DELETE
- `tests/property/market/derivatives/normalization/test_canonical_stability.py`: DELETE
- `tests/property/market/derivatives/option_chain/__pycache__/__init__.cpython-311.pyc`: DELETE
- `tests/property/market/derivatives/option_chain/__pycache__/test_option_chain_properties.cpython-311-pytest-8.4.2.pyc`: DELETE
- `tests/property/market/derivatives/option_chain/test_option_chain_properties.py`: DELETE
- `tests/property/market/derivatives/replay_data/__pycache__/__init__.cpython-311.pyc`: DELETE
- `tests/property/market/derivatives/replay_data/__pycache__/test_d03_temporal_properties.cpython-311-pytest-8.4.2.pyc`: DELETE
- `tests/property/market/derivatives/replay_data/test_d03_temporal_properties.py`: DELETE
- `tests/unit/market/data_acquisition/__pycache__/__init__.cpython-311.pyc`: DELETE
- `tests/unit/market/data_acquisition/__pycache__/test_real_session_ingestion.cpython-311-pytest-8.4.2.pyc`: DELETE
- `tests/unit/market/data_acquisition/test_real_session_ingestion.py`: DELETE
- `tests/unit/market/derivatives/__init__.py`: DELETE
- `tests/unit/market/derivatives/__pycache__/__init__.cpython-311.pyc`: DELETE
- `tests/unit/market/derivatives/acquisition/__pycache__/__init__.cpython-311.pyc`: DELETE
- `tests/unit/market/derivatives/acquisition/__pycache__/test_client.cpython-311-pytest-8.4.2.pyc`: DELETE
- `tests/unit/market/derivatives/acquisition/__pycache__/test_parsers.cpython-311-pytest-8.4.2.pyc`: DELETE
- `tests/unit/market/derivatives/acquisition/__pycache__/test_plan.cpython-311-pytest-8.4.2.pyc`: DELETE
- `tests/unit/market/derivatives/acquisition/__pycache__/test_redaction.cpython-311-pytest-8.4.2.pyc`: DELETE
- `tests/unit/market/derivatives/acquisition/__pycache__/test_secrets.cpython-311-pytest-8.4.2.pyc`: DELETE
- `tests/unit/market/derivatives/acquisition/test_client.py`: DELETE
- `tests/unit/market/derivatives/acquisition/test_parsers.py`: DELETE
- `tests/unit/market/derivatives/acquisition/test_plan.py`: DELETE
- `tests/unit/market/derivatives/acquisition/test_redaction.py`: DELETE
- `tests/unit/market/derivatives/acquisition/test_secrets.py`: DELETE
- `tests/unit/market/derivatives/active_window/__init__.py`: DELETE
- `tests/unit/market/derivatives/active_window/__pycache__/__init__.cpython-311.pyc`: DELETE
- `tests/unit/market/derivatives/active_window/__pycache__/test_cache.cpython-311-pytest-8.4.2.pyc`: DELETE
- `tests/unit/market/derivatives/active_window/__pycache__/test_engine.cpython-311-pytest-8.4.2.pyc`: DELETE
- `tests/unit/market/derivatives/active_window/test_cache.py`: DELETE
- `tests/unit/market/derivatives/active_window/test_engine.py`: DELETE
- `tests/unit/market/derivatives/artifacts/__pycache__/__init__.cpython-311.pyc`: DELETE
- `tests/unit/market/derivatives/artifacts/__pycache__/test_artifact_provenance.cpython-311-pytest-8.4.2.pyc`: DELETE
- `tests/unit/market/derivatives/artifacts/__pycache__/test_store.cpython-311-pytest-8.4.2.pyc`: DELETE
- `tests/unit/market/derivatives/artifacts/test_artifact_provenance.py`: DELETE
- `tests/unit/market/derivatives/artifacts/test_store.py`: DELETE
- `tests/unit/market/derivatives/contract_master/__init__.py`: DELETE
- `tests/unit/market/derivatives/contract_master/__pycache__/__init__.cpython-311.pyc`: DELETE
- `tests/unit/market/derivatives/contract_master/__pycache__/expiry_helpers.cpython-311.pyc`: DELETE
- `tests/unit/market/derivatives/contract_master/__pycache__/helpers.cpython-311.pyc`: DELETE
- `tests/unit/market/derivatives/contract_master/__pycache__/test_expiry_engine.cpython-311-pytest-8.4.2.pyc`: DELETE
- `tests/unit/market/derivatives/contract_master/__pycache__/test_normalization.cpython-311-pytest-8.4.2.pyc`: DELETE
- `tests/unit/market/derivatives/contract_master/__pycache__/test_registry.cpython-311-pytest-8.4.2.pyc`: DELETE
- `tests/unit/market/derivatives/contract_master/expiry_helpers.py`: DELETE
- `tests/unit/market/derivatives/contract_master/helpers.py`: DELETE
- `tests/unit/market/derivatives/contract_master/test_expiry_engine.py`: DELETE
- `tests/unit/market/derivatives/contract_master/test_normalization.py`: DELETE
- `tests/unit/market/derivatives/contract_master/test_registry.py`: DELETE
- `tests/unit/market/derivatives/normalization/__pycache__/__init__.cpython-311.pyc`: DELETE
- `tests/unit/market/derivatives/normalization/__pycache__/test_normalizer.cpython-311-pytest-8.4.2.pyc`: DELETE
- `tests/unit/market/derivatives/normalization/test_normalizer.py`: DELETE
- `tests/unit/market/derivatives/option_chain/__init__.py`: DELETE
- `tests/unit/market/derivatives/option_chain/__pycache__/__init__.cpython-311.pyc`: DELETE
- `tests/unit/market/derivatives/option_chain/__pycache__/helpers.cpython-311.pyc`: DELETE
- `tests/unit/market/derivatives/option_chain/__pycache__/test_builder.cpython-311-pytest-8.4.2.pyc`: DELETE
- `tests/unit/market/derivatives/option_chain/__pycache__/test_features.cpython-311-pytest-8.4.2.pyc`: DELETE
- `tests/unit/market/derivatives/option_chain/__pycache__/test_greeks_calculator.cpython-311-pytest-8.4.2.pyc`: DELETE
- `tests/unit/market/derivatives/option_chain/helpers.py`: DELETE
- `tests/unit/market/derivatives/option_chain/test_builder.py`: DELETE
- `tests/unit/market/derivatives/option_chain/test_features.py`: DELETE
- `tests/unit/market/derivatives/option_chain/test_greeks_calculator.py`: DELETE
- `tests/unit/market/derivatives/providers/__pycache__/__init__.cpython-311.pyc`: DELETE
- `tests/unit/market/derivatives/providers/__pycache__/test_provenance.cpython-311-pytest-8.4.2.pyc`: DELETE
- `tests/unit/market/derivatives/providers/test_provenance.py`: DELETE
- `tests/unit/market/derivatives/replay_data/__pycache__/__init__.cpython-311.pyc`: DELETE
- `tests/unit/market/derivatives/replay_data/__pycache__/test_builder.cpython-311-pytest-8.4.2.pyc`: DELETE
- `tests/unit/market/derivatives/replay_data/__pycache__/test_resampler.cpython-311-pytest-8.4.2.pyc`: DELETE
- `tests/unit/market/derivatives/replay_data/test_builder.py`: DELETE
- `tests/unit/market/derivatives/replay_data/test_resampler.py`: DELETE
- `tests/unit/market/derivatives/strike_window/__init__.py`: DELETE
- `tests/unit/market/derivatives/strike_window/__pycache__/__init__.cpython-311.pyc`: DELETE
- `tests/unit/market/derivatives/strike_window/__pycache__/helpers.cpython-311.pyc`: DELETE
- `tests/unit/market/derivatives/strike_window/__pycache__/test_strike_window.cpython-311-pytest-8.4.2.pyc`: DELETE
- `tests/unit/market/derivatives/strike_window/helpers.py`: DELETE
- `tests/unit/market/derivatives/strike_window/test_strike_window.py`: DELETE
- `tests/unit/market/feeds/upstox_v3/__init__.py`: DELETE
- `tests/unit/market/feeds/upstox_v3/__pycache__/__init__.cpython-311.pyc`: DELETE
- `tests/unit/market/feeds/upstox_v3/__pycache__/helpers.cpython-311.pyc`: DELETE
- `tests/unit/market/feeds/upstox_v3/__pycache__/test_adapter.cpython-311-pytest-8.4.2.pyc`: DELETE
- `tests/unit/market/feeds/upstox_v3/__pycache__/test_codec.cpython-311-pytest-8.4.2.pyc`: DELETE
- `tests/unit/market/feeds/upstox_v3/__pycache__/test_frames.cpython-311-pytest-8.4.2.pyc`: DELETE
- `tests/unit/market/feeds/upstox_v3/__pycache__/test_freshness.cpython-311-pytest-8.4.2.pyc`: DELETE
- `tests/unit/market/feeds/upstox_v3/__pycache__/test_protobuf_codec.cpython-311-pytest-8.4.2.pyc`: DELETE
- `tests/unit/market/feeds/upstox_v3/__pycache__/test_subscription.cpython-311-pytest-8.4.2.pyc`: DELETE
- `tests/unit/market/feeds/upstox_v3/__pycache__/test_transport.cpython-311-pytest-8.4.2.pyc`: DELETE
- `tests/unit/market/feeds/upstox_v3/helpers.py`: DELETE
- `tests/unit/market/feeds/upstox_v3/test_adapter.py`: DELETE
- `tests/unit/market/feeds/upstox_v3/test_codec.py`: DELETE
- `tests/unit/market/feeds/upstox_v3/test_frames.py`: DELETE
- `tests/unit/market/feeds/upstox_v3/test_freshness.py`: DELETE
- `tests/unit/market/feeds/upstox_v3/test_protobuf_codec.py`: DELETE
- `tests/unit/market/feeds/upstox_v3/test_subscription.py`: DELETE
- `tests/unit/market/feeds/upstox_v3/test_transport.py`: DELETE
- `tests/unit/market/providers/upstox/__pycache__/__init__.cpython-311.pyc`: DELETE
- `tests/unit/market/providers/upstox/__pycache__/test_capabilities.cpython-311-pytest-8.4.2.pyc`: DELETE
- `tests/unit/market/providers/upstox/test_capabilities.py`: DELETE
- `verify_all_features.py`: DELETE
