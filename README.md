# Autonomous Trading System (ATS)

ATS currently implements **M010-00 repository bootstrap only**.

The alpha target is A0 Research, A1 Signals, and A2 Autonomous Paper Trading.

Currently not implemented: trading strategies, market feed, Kronos, policy compiler,
risk engine, execution, PaperBroker, broker integrations, real-money trading,
browser trading, or A3+ capabilities.

> **AI proposes; deterministic ATS authorizes.**

## Bootstrap validation

Pinned tools are Python 3.11.15, Node 26.4.0, uv 0.12.1, and pnpm 11.9.0.

```text
uv sync --frozen
uv run python -m pytest tests/smoke
uv run ruff check backend
uv run mypy backend/src
pnpm install --frozen-lockfile
pnpm -r typecheck
pnpm -r test --if-present
```
