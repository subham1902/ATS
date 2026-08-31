"""Immutable A2 forward-paper validation evidence and reporting.

This module deliberately wraps the A2 orchestrator rather than implementing
orders, fills, risk, or reconciliation.  Its file ledger is append-only: a
session result is immutable evidence, never a tuning input or deletable row.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from statistics import median
from typing import Any
from uuid import uuid4

from ats.trading_runtime.reconciliation import SessionReconciliation


class ValidationSource(StrEnum):
    PAPER_FORWARD = "PAPER_FORWARD"
    REPLAY = "REPLAY"


def require_paper_only(execution_mode: str | None) -> None:
    """Reject LIVE, UNKNOWN, and missing execution modes before startup."""
    if execution_mode != "PAPER":
        raise RuntimeError("forward validation requires explicit execution_mode=PAPER")


def cohort_id(*, code_version: str, strategy_version: str, policy_version: str) -> str:
    """Version-derived cohort identity; a version change cannot mix evidence."""
    payload = "|".join((code_version, strategy_version, policy_version)).encode()
    return hashlib.sha256(payload).hexdigest()[:16]


@dataclass(frozen=True)
class ForwardValidationResult:
    session_id: str
    source: ValidationSource
    code_version: str
    strategy_version: str
    policy_version: str
    cohort_id: str
    completed_at: str
    reconciliation: dict[str, object]
    fills: int
    exits: int
    abstentions: int
    execution_failures: int
    regimes: tuple[str, ...] = ()

    @classmethod
    def from_reconciliation(
        cls,
        *,
        source: ValidationSource,
        code_version: str,
        strategy_version: str,
        policy_version: str,
        report: SessionReconciliation,
        fills: int,
        exits: int,
        abstentions: int = 0,
        execution_failures: int = 0,
        regimes: tuple[str, ...] = (),
    ) -> ForwardValidationResult:
        return cls(
            session_id=str(uuid4()), source=source, code_version=code_version,
            strategy_version=strategy_version, policy_version=policy_version,
            cohort_id=cohort_id(
                code_version=code_version,
                strategy_version=strategy_version,
                policy_version=policy_version,
            ),
            completed_at=datetime.now(UTC).isoformat(), reconciliation=report.to_dict(),
            fills=fills, exits=exits, abstentions=abstentions,
            execution_failures=execution_failures, regimes=regimes,
        )

    @property
    def net_pnl(self) -> Decimal:
        return Decimal(str(self.reconciliation["net_realized_pnl"]))


class ForwardValidationLedger:
    """Append-only JSONL evidence store with cohort/source integrity guards."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def results(self) -> tuple[ForwardValidationResult, ...]:
        if not self.path.exists():
            return ()
        return tuple(
            ForwardValidationResult(**json.loads(line))
            for line in self.path.read_text(encoding="utf-8").splitlines() if line
        )

    def append(self, result: ForwardValidationResult) -> None:
        prior = self.results()
        if any(item.session_id == result.session_id for item in prior):
            raise ValueError("session result already recorded")
        cohort = [item for item in prior if item.cohort_id == result.cohort_id]
        if cohort and any(item.source is not result.source for item in cohort):
            raise ValueError("REPLAY and PAPER_FORWARD evidence cannot share a cohort")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(_as_json(result), sort_keys=True, separators=(",", ":")) + "\n")


class ValidationListener:
    """Orchestrator listener that persists only the final reconciled result."""

    def __init__(
        self, *, ledger: ForwardValidationLedger, source: ValidationSource,
        code_version: str, strategy_version: str, policy_version: str,
        regimes: tuple[str, ...] = (),
    ) -> None:
        self.ledger = ledger
        self.source = source
        self.code_version = code_version
        self.strategy_version = strategy_version
        self.policy_version = policy_version
        self.regimes = regimes
        self.fills = 0
        self.exits = 0
        self.abstentions = 0
        self.execution_failures = 0
        self.result: ForwardValidationResult | None = None

    def on_decision(self, decision: Any, **kwargs: Any) -> None:
        _ = kwargs
        value = str(decision)
        if value.endswith("PASS") or value.endswith("BLOCKED"):
            self.abstentions += 1
        if value.endswith("REJECTED"):
            self.execution_failures += 1

    def on_fill(self, order_id: str, instrument_id: str, quantity: Decimal, price: Decimal) -> None:
        _ = (order_id, instrument_id, quantity, price)
        self.fills += 1

    def on_exit(self, position_id: str, reason: str) -> None:
        _ = (position_id, reason)
        self.exits += 1

    def on_session_end(self, report: SessionReconciliation) -> None:
        if not report.closed_successfully:
            raise RuntimeError("cannot persist an unreconciled validation session")
        result = ForwardValidationResult.from_reconciliation(
            source=self.source, code_version=self.code_version,
            strategy_version=self.strategy_version, policy_version=self.policy_version,
            report=report, fills=self.fills, exits=self.exits,
            abstentions=self.abstentions, execution_failures=self.execution_failures,
            regimes=self.regimes,
        )
        self.ledger.append(result)
        self.result = result


@dataclass(frozen=True)
class AggregateValidationReport:
    source: ValidationSource
    cohort_id: str
    sessions: int
    trades: int
    total_net_pnl: Decimal
    median_net_pnl: Decimal | None
    expectancy: Decimal | None
    profit_factor: Decimal | None
    max_drawdown: Decimal
    consecutive_losses: int
    cost_impact: Decimal
    operational_failures: int
    sufficient_samples: bool
    conclusion: str
    regime_performance: dict[str, Decimal]


def aggregate(
    results: tuple[ForwardValidationResult, ...],
    *,
    minimum_sessions: int = 20,
    minimum_trades: int = 100,
) -> AggregateValidationReport:
    if not results:
        raise ValueError("no validation sessions")
    source, cohort = results[0].source, results[0].cohort_id
    if any(item.source is not source or item.cohort_id != cohort for item in results):
        raise ValueError("aggregate requires one source and one validation cohort")
    pnls = [item.net_pnl for item in results]
    trades = sum(int(str(item.reconciliation["total_trades"])) for item in results)
    winners = sum((p for p in pnls if p > 0), Decimal("0"))
    losers = -sum((p for p in pnls if p < 0), Decimal("0"))
    streak = current = 0
    for pnl in pnls:
        current = current + 1 if pnl < 0 else 0
        streak = max(streak, current)
    regimes: dict[str, Decimal] = {}
    for item in results:
        for regime in item.regimes:
            regimes[regime] = regimes.get(regime, Decimal("0")) + item.net_pnl
    sufficient = len(results) >= minimum_sessions and trades >= minimum_trades
    costs = sum(
        (
            Decimal(str(item.reconciliation["fees"]))
            + Decimal(str(item.reconciliation["taxes"]))
            + Decimal(str(item.reconciliation["slippage_cost"]))
            for item in results
        ),
        Decimal("0"),
    )
    return AggregateValidationReport(
        source=source,
        cohort_id=cohort,
        sessions=len(results),
        trades=trades,
        total_net_pnl=sum(pnls, Decimal("0")),
        median_net_pnl=Decimal(str(median(pnls))) if pnls else None,
        expectancy=sum(pnls, Decimal("0")) / Decimal(trades) if trades else None,
        profit_factor=(winners / losers) if losers else None,
        max_drawdown=max(Decimal(str(item.reconciliation["max_drawdown"])) for item in results),
        consecutive_losses=streak,
        cost_impact=costs,
        operational_failures=sum(item.execution_failures for item in results),
        sufficient_samples=sufficient,
        conclusion=(
            "INSUFFICIENT_SAMPLE"
            if not sufficient
            else "EVIDENCE_COLLECTED_NOT_PROFITABILITY_PROOF"
        ),
        regime_performance=regimes,
    )


def _as_json(value: ForwardValidationResult) -> dict[str, object]:
    return {**value.__dict__, "source": value.source.value, "regimes": list(value.regimes)}


__all__ = [
    "AggregateValidationReport",
    "ForwardValidationLedger",
    "ForwardValidationResult",
    "ValidationListener",
    "ValidationSource",
    "aggregate",
    "cohort_id",
    "require_paper_only",
]
