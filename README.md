# ATS — Autonomous Trading System

ATS is a deterministic, event-driven autonomous trading system. The architecture
follows the principle **"AI proposes; deterministic ATS authorizes."** Research and
advisory components propose, while the deterministic contracts/kernel layer is the
sole authority for authorization and execution.

## Repository layout

- `backend/src/ats` — core system modules:
  - `contracts/`, `kernel/` — the deterministic authorization core
  - `market/` — market data feeds and derivatives acquisition (incl. Upstox V3 feed/codec)
  - `forecast/`, `intelligence/` — features, regime, calibration, thesis, ensemble, strategy lab
  - `execution/`, `portfolio/`, `governance/`, `events/`, `persistence/`, `observability/`
  - `trading_runtime/` — runtime engine and broker adapters
  - `api/` — service interface
- `frontend/` — control center UI (`apps/control-center`, `packages/ui`, `packages/api-client`)
- `tests/` — contract, integration, unit, property, acceptance, e2e, faults, smoke
- `benchmarks/`, `scripts/`, `docs/`

## Status

The modules above are implemented in this repository and covered by the test suite.
Replay/backtest and paper/paper-testnet paths exist under `trading_runtime` and the
strategy lab. Trading is NOT proven to be profitable by repository evidence, and no
live-broker trading capability is asserted here. Treat all performance claims as
development/experimental only.

## Bootstrap / validation

```text
uv sync --frozen
uv run python -m pytest tests/smoke
uv run ruff check backend
uv run mypy backend/src
pnpm install --frozen-lockfile
pnpm -r typecheck
pnpm -r test --if-present
```

Pinned toolchain: Python 3.11.15, Node 24.19.0, uv 0.12.1, pnpm 11.9.0.
