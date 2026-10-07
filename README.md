# ATS — XAUUSD Laboratory

ATS is a deterministic XAUUSD research and trading laboratory: AI and managed
agents propose; the ATS authorization kernel and portfolio authority authorize.
MetaTrader supplies broker observations through `market/metatrader/`. Step 1 adds
encrypted multi-account connections and monitoring for demo and live accounts.
Execution currently remains internal paper execution; external demo/live routing
is scheduled for Step 3, through separate account-bound authority. MT4 authenticated
account support remains NOT_CONFIGURED until a reliable bridge exists.

The XAUUSD-specialized ATS currently has no repository evidence establishing profitability.
Performance from removed markets does not transfer. Surviving strategies are research-only.

## Operator surfaces

Dashboard, Market, Research, Strategies, Agents, Accounts, Paper Trading, Datasets,
System. The market is always XAUUSD. Broker suffixes and GOLD aliases map to that
identity. With multiple connected accounts, select the data account explicitly
on Market; quotes from different accounts are never blended.

Accounts offers **Connect Only** and **Connect & Enable Execution**. The latter
records operator consent in Step 1, while displaying that order routing is
unavailable. Risk limits, strategy association and external authority remain
required in Step 3. Connection mode alone never grants financial authority.

Passwords and login values are encrypted with user-bound Windows DPAPI; the
registry stores references. Concurrent MT5 accounts require separate terminal
installations/data profiles. No SDK order functions exist in the current connector.

## Market and dataset truth

Live and CSV/Parquet replay use immutable canonical observations, UTC timestamps,
versioned datasets and explicit quality reports. Future ticks, unclosed bars,
unsupported symbols and unknown broker terms fail closed. Missing information
stays unknown. Footprints are labelled BROKER_TICK_PROXY; tick volume is distinct
from real broker-reported volume, and inferred direction is not exchange order flow.

The local terminal currently reports ticks approximately three hours ahead of UTC.
ATS rejects these observations; no guessed timezone correction is applied.

## Validation

Pinned: Python 3.11.15, Node 24.19.0, uv 0.12.1, pnpm 11.9.0.

```text
uv sync --frozen
uv run --no-sync ruff check backend tests
uv run --no-sync mypy backend/src
uv run --no-sync python -m pytest tests backend/tests -q
pnpm install --frozen-lockfile
pnpm format:check
pnpm lint
pnpm -r typecheck
pnpm -r test
pnpm --filter @ats/control-center build
```

Set ATS_TEST_POSTGRES_DSN to an isolated test database to run durability tests.
Tests redirect product writes to temporary roots and mock account transports.
Port 3000 belongs to another application and must remain untouched.

Architecture: [specialization](docs/architecture/XAUUSD_MT5_SPECIALIZATION.md)
and [account foundation](docs/architecture/METATRADER_MULTI_ACCOUNT_EXECUTION.md).
