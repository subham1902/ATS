"""Explainable bounded portfolio allocation; A04 remains final authority."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from decimal import ROUND_FLOOR, Decimal
from uuid import uuid4

from ats.contracts.domain.hashing import compute_payload_hash
from ats.contracts.domain.types import LossState
from ats.trading_runtime.hwm import ProfitProtectionState
from ats.trading_runtime.modes import TradingMode

from .models import (
    AllocationOutcome,
    CandidateAllocationRequest,
    PortfolioAllocationDecision,
    PortfolioBrainContext,
    PortfolioReview,
    PortfolioReviewAction,
)


@dataclass(frozen=True, slots=True)
class PortfolioBrainPolicy:
    utilization: dict[TradingMode, Decimal]
    maximum_positions: dict[TradingMode, int]
    minimum_net_value: dict[TradingMode, Decimal]
    maximum_spread_fraction: dict[TradingMode, Decimal]
    minimum_liquidity: dict[TradingMode, Decimal]
    decision_ttl: timedelta = timedelta(seconds=5)


DEFAULT_PORTFOLIO_BRAIN_POLICY = PortfolioBrainPolicy(
    utilization={
        TradingMode.SAFE: Decimal("0.30"),
        TradingMode.NORMAL: Decimal("0.60"),
        TradingMode.AGGRESSIVE: Decimal("0.80"),
    },
    maximum_positions={
        TradingMode.SAFE: 1,
        TradingMode.NORMAL: 2,
        TradingMode.AGGRESSIVE: 4,
    },
    minimum_net_value={
        TradingMode.SAFE: Decimal("20"),
        TradingMode.NORMAL: Decimal("10"),
        TradingMode.AGGRESSIVE: Decimal("1"),
    },
    maximum_spread_fraction={
        TradingMode.SAFE: Decimal("0.02"),
        TradingMode.NORMAL: Decimal("0.04"),
        TradingMode.AGGRESSIVE: Decimal("0.06"),
    },
    minimum_liquidity={
        TradingMode.SAFE: Decimal("0.80"),
        TradingMode.NORMAL: Decimal("0.60"),
        TradingMode.AGGRESSIVE: Decimal("0.40"),
    },
)


class PortfolioManagerBrain:
    """Uses a caller-supplied authority snapshot and never reserves or spends capital."""

    def __init__(self, policy: PortfolioBrainPolicy = DEFAULT_PORTFOLIO_BRAIN_POLICY) -> None:
        self._policy = policy

    def allocate(
        self, request: CandidateAllocationRequest, context: PortfolioBrainContext
    ) -> PortfolioAllocationDecision:
        reasons: list[str] = []
        mode = self._deescalated_mode(context, reasons)
        denial = self._hard_denial(request, context, mode)
        if denial is not None:
            return self._decision(
                request,
                context,
                mode,
                AllocationOutcome.DENY,
                Decimal(0),
                Decimal(0),
                denial,
                (Decimal(0),) * 5,
            )
        if len(context.positions) >= self._policy.maximum_positions[mode]:
            return self._decision(
                request,
                context,
                mode,
                AllocationOutcome.DEFER,
                Decimal(0),
                Decimal(0),
                ("POSITION_CAPACITY_REACHED",),
                (Decimal(0),) * 5,
            )

        correlation = (
            Decimal("0.25")
            if any(
                item.underlying != request.underlying and item.direction is request.direction
                for item in context.positions
            )
            else Decimal(0)
        )
        underlying = (
            Decimal("0.25")
            if any(item.underlying == request.underlying for item in context.positions)
            else Decimal(0)
        )
        strategy = (
            Decimal("0.15")
            if any(
                item.strategy_id == request.candidate.strategy_definition_id
                for item in context.positions
            )
            else Decimal(0)
        )
        concentration = min(Decimal("0.50"), underlying + strategy)
        drawdown = min(Decimal("0.50"), context.hwm.drawdown_fraction * Decimal(4))
        execution = Decimal(0) if context.execution_healthy else Decimal("1")
        liquidity = max(Decimal(0), Decimal("1") - request.liquidity_score) * Decimal("0.25")
        penalty = min(
            Decimal("0.90"), correlation + concentration + drawdown + execution + liquidity
        )
        account = context.snapshot.account
        capacity = min(
            request.requested_capital,
            account.available_capital,
            account.deployable_capital * self._policy.utilization[mode],
            context.remaining_session_risk,
        )
        approved = (capacity * (Decimal(1) - penalty)).quantize(Decimal("0.01"))
        if approved < request.maximum_loss or approved <= 0:
            return self._decision(
                request,
                context,
                mode,
                AllocationOutcome.DENY,
                Decimal(0),
                Decimal(0),
                ("INSUFFICIENT_RISK_BUDGET",),
                (correlation, concentration, drawdown, execution, liquidity),
            )
        ratio = approved / request.requested_capital
        quantity = (request.requested_quantity * ratio).to_integral_value(rounding=ROUND_FLOOR)
        if quantity <= 0:
            return self._decision(
                request,
                context,
                mode,
                AllocationOutcome.DENY,
                Decimal(0),
                Decimal(0),
                ("QUANTITY_REDUCED_TO_ZERO",),
                (correlation, concentration, drawdown, execution, liquidity),
            )
        outcome = (
            AllocationOutcome.ALLOW
            if approved == request.requested_capital
            else AllocationOutcome.ALLOW_REDUCED
        )
        reasons.append("PORTFOLIO_ALLOCATION_PERMITTED")
        if outcome is AllocationOutcome.ALLOW_REDUCED:
            reasons.append("PORTFOLIO_PENALTY_REDUCED_SIZE")
        return self._decision(
            request,
            context,
            mode,
            outcome,
            approved,
            quantity,
            tuple(reasons),
            (correlation, concentration, drawdown, execution, liquidity),
        )

    def review(self, context: PortfolioBrainContext) -> PortfolioReview:
        reasons: list[str] = []
        mode = self._deescalated_mode(context, reasons)
        if mode is TradingMode.HALTED:
            action = PortfolioReviewAction.EXIT_RECOMMENDED
        elif mode is not context.effective_mode:
            action = PortfolioReviewAction.DEESCALATE_MODE
        elif not context.feed_healthy or not context.execution_healthy:
            action = PortfolioReviewAction.BLOCK_NEW_DIRECTION
        elif context.hwm.profit_protection is ProfitProtectionState.TRIGGERED:
            action = PortfolioReviewAction.REDUCE
        else:
            action = PortfolioReviewAction.KEEP
            reasons.append("PORTFOLIO_WITHIN_ENVELOPE")
        return PortfolioReview(action=action, effective_mode=mode, reason_codes=tuple(reasons))

    def _hard_denial(
        self,
        request: CandidateAllocationRequest,
        context: PortfolioBrainContext,
        mode: TradingMode,
    ) -> tuple[str, ...] | None:
        if mode is TradingMode.HALTED or context.snapshot.account.loss_state is LossState.HALTED:
            return ("PORTFOLIO_HALTED",)
        if not context.feed_healthy or not request.quote_fresh:
            return ("MARKET_DATA_UNSAFE",)
        if not context.execution_healthy:
            return ("EXECUTION_UNHEALTHY",)
        if request.expected_net_value < self._policy.minimum_net_value[mode]:
            return ("EXPECTED_NET_VALUE_TOO_LOW",)
        if request.spread_fraction > self._policy.maximum_spread_fraction[mode]:
            return ("SPREAD_TOO_WIDE",)
        if request.liquidity_score < self._policy.minimum_liquidity[mode]:
            return ("LIQUIDITY_TOO_LOW",)
        return None

    @staticmethod
    def _deescalated_mode(context: PortfolioBrainContext, reasons: list[str]) -> TradingMode:
        mode = context.effective_mode
        if context.snapshot.account.loss_state is LossState.HALTED:
            reasons.append("LOSS_STATE_HALTED")
            return TradingMode.HALTED
        if not context.feed_healthy or not context.execution_healthy:
            reasons.append("INFRASTRUCTURE_DEGRADED")
            return TradingMode.SAFE
        if context.loss_streak >= 3 or not context.calibration_healthy:
            reasons.append("PERFORMANCE_DEGRADED")
            return TradingMode.SAFE
        if (
            context.hwm.mode_hint is not None
            and context.hwm.mode_hint is not TradingMode.AGGRESSIVE
        ):
            reasons.append("HWM_DEESCALATION")
            return context.hwm.mode_hint
        return mode

    def _decision(
        self,
        request: CandidateAllocationRequest,
        context: PortfolioBrainContext,
        mode: TradingMode,
        outcome: AllocationOutcome,
        capital: Decimal,
        quantity: Decimal,
        reasons: tuple[str, ...],
        penalties: tuple[Decimal, Decimal, Decimal, Decimal, Decimal],
    ) -> PortfolioAllocationDecision:
        draft = PortfolioAllocationDecision(
            decision_id=uuid4(),
            candidate_id=request.candidate.candidate_id,
            candidate_hash=request.candidate.payload_hash,
            outcome=outcome,
            approved_capital=capital,
            approved_quantity=quantity,
            expected_net_value=request.expected_net_value,
            effective_mode=mode,
            correlation_penalty=penalties[0],
            concentration_penalty=penalties[1],
            drawdown_penalty=penalties[2],
            execution_penalty=penalties[3],
            liquidity_penalty=penalties[4],
            reason_codes=reasons,
            input_hash=context.input_hash,
            valid_until=context.as_of + self._policy.decision_ttl,
            payload_hash="0" * 64,
        )
        return draft.model_copy(update={"payload_hash": compute_payload_hash(draft)})


__all__ = ["DEFAULT_PORTFOLIO_BRAIN_POLICY", "PortfolioBrainPolicy", "PortfolioManagerBrain"]
