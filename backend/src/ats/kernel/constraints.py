"""Deterministic strictest-wins constraint composition."""

from __future__ import annotations

from decimal import Decimal
from typing import TypeVar
from uuid import UUID

from ats.contracts.domain.models import StrategyPolicy
from ats.contracts.domain.types import MoneyOrPortfolioFraction, ValueKind
from ats.contracts.governance.models import TradingCampaign
from ats.contracts.governance.types import (
    ConstraintCode,
    ConstraintProvenance,
    ConstraintSource,
    EffectiveConstraintSet,
    StrategyExecutionMode,
)
from ats.contracts.hashing import canonicalize

from .types import ConstraintComposition, RiskCapitalBasis, SystemConstraintSet

T = TypeVar("T")


def resolve_authority_value(
    value: MoneyOrPortfolioFraction,
    *,
    basis: RiskCapitalBasis | None,
    campaign_basis: bool = False,
) -> Decimal:
    if value.kind is ValueKind.MONEY:
        return value.value
    if basis is None:
        raise ValueError("portfolio fraction requires RiskCapitalBasis")
    base = basis.campaign_equity_basis if campaign_basis else basis.portfolio_equity
    return value.value * base


def _strict_money(
    values: tuple[tuple[ConstraintSource, UUID, MoneyOrPortfolioFraction], ...],
    *,
    basis: RiskCapitalBasis | None,
    campaign_basis: bool = False,
) -> tuple[MoneyOrPortfolioFraction, ConstraintSource]:
    selected = min(
        values,
        key=lambda item: resolve_authority_value(
            item[2], basis=basis, campaign_basis=campaign_basis
        ),
    )
    amount = resolve_authority_value(selected[2], basis=basis, campaign_basis=campaign_basis)
    return MoneyOrPortfolioFraction(kind=ValueKind.MONEY, value=amount), selected[0]


def _minimum(
    values: tuple[tuple[ConstraintSource, UUID, T], ...],
) -> tuple[T, ConstraintSource]:
    selected = min(values, key=lambda item: item[2])  # type: ignore[arg-type,return-value]
    return selected[2], selected[0]


def _maximum(
    values: tuple[tuple[ConstraintSource, UUID, T], ...],
) -> tuple[T, ConstraintSource]:
    selected = max(values, key=lambda item: item[2])  # type: ignore[arg-type,return-value]
    return selected[2], selected[0]


def _intersection(*values: tuple[T, ...]) -> tuple[T, ...]:
    intersection = set(values[0])
    for value in values[1:]:
        intersection.intersection_update(value)
    if not intersection:
        raise ValueError("required allowlist intersection is empty")
    return tuple(sorted(intersection, key=repr))


def compose_constraints(
    system: SystemConstraintSet,
    policy: StrategyPolicy,
    campaign: TradingCampaign,
    *,
    capital_basis: RiskCapitalBasis | None,
) -> ConstraintComposition:
    system_ref = system.constraint_set_id
    policy_ref = policy.policy_id
    campaign_ref = campaign.campaign_id
    refs = (system_ref, policy_ref, campaign_ref)
    maximum_loss, loss_source = _strict_money(
        (
            (ConstraintSource.SYSTEM, system_ref, system.maximum_loss_per_trade),
            (ConstraintSource.POLICY, policy_ref, policy.maximum_loss),
            (ConstraintSource.CAMPAIGN, campaign_ref, campaign.maximum_loss_per_trade),
        ),
        basis=capital_basis,
    )
    policy_campaign_loss = MoneyOrPortfolioFraction(
        kind=ValueKind.MONEY, value=policy.daily_loss_limit
    )
    maximum_campaign_loss, campaign_loss_source = _strict_money(
        (
            (ConstraintSource.SYSTEM, system_ref, system.maximum_campaign_loss),
            (ConstraintSource.POLICY, policy_ref, policy_campaign_loss),
            (ConstraintSource.CAMPAIGN, campaign_ref, campaign.maximum_campaign_loss),
        ),
        basis=capital_basis,
        campaign_basis=True,
    )
    budget_per_trade, budget_source = _strict_money(
        (
            (ConstraintSource.SYSTEM, system_ref, system.maximum_budget_per_trade),
            (ConstraintSource.CAMPAIGN, campaign_ref, campaign.maximum_budget_per_trade),
        ),
        basis=capital_basis,
    )
    drawdown, drawdown_source = _minimum(
        (
            (ConstraintSource.SYSTEM, system_ref, system.drawdown_limit),
            (ConstraintSource.POLICY, policy_ref, policy.drawdown_limit),
            (ConstraintSource.CAMPAIGN, campaign_ref, campaign.drawdown_limit),
        )
    )
    max_trades, max_trades_source = _minimum(
        (
            (ConstraintSource.SYSTEM, system_ref, system.max_trades),
            (ConstraintSource.CAMPAIGN, campaign_ref, campaign.max_trades),
        )
    )
    concurrency, concurrency_source = _minimum(
        (
            (ConstraintSource.SYSTEM, system_ref, system.max_concurrent_positions),
            (
                ConstraintSource.POLICY,
                policy_ref,
                policy.portfolio_constraints.maximum_open_positions,
            ),
            (ConstraintSource.CAMPAIGN, campaign_ref, campaign.max_concurrent_positions),
        )
    )
    capital, capital_source = _minimum(
        (
            (ConstraintSource.SYSTEM, system_ref, system.capital_budget),
            (ConstraintSource.CAMPAIGN, campaign_ref, campaign.capital_budget),
        )
    )
    probability, probability_source = _maximum(
        (
            (ConstraintSource.SYSTEM, system_ref, system.minimum_calibrated_probability),
            (ConstraintSource.POLICY, policy_ref, policy.confidence_threshold),
            (
                ConstraintSource.CAMPAIGN,
                campaign_ref,
                campaign.minimum_calibrated_probability,
            ),
        )
    )
    support, support_source = _maximum(
        (
            (ConstraintSource.SYSTEM, system_ref, system.minimum_calibration_support),
            (ConstraintSource.POLICY, policy_ref, policy.minimum_calibration_support),
            (ConstraintSource.CAMPAIGN, campaign_ref, campaign.minimum_calibration_support),
        )
    )
    edge, edge_source = _maximum(
        (
            (ConstraintSource.SYSTEM, system_ref, system.minimum_expected_edge_r),
            (ConstraintSource.CAMPAIGN, campaign_ref, campaign.minimum_expected_edge_r),
        )
    )
    reward_risk, reward_source = _maximum(
        (
            (ConstraintSource.SYSTEM, system_ref, system.minimum_reward_risk),
            (ConstraintSource.POLICY, policy_ref, policy.minimum_reward_risk),
            (ConstraintSource.CAMPAIGN, campaign_ref, campaign.minimum_reward_risk),
        )
    )
    instruments = _intersection(
        system.allowed_instruments, policy.universe, campaign.instrument_universe
    )
    timeframes = _intersection(
        system.allowed_timeframes, (policy.timeframe,), campaign.allowed_timeframes
    )
    strategies = _intersection(system.allowed_strategies, campaign.allowed_strategies)
    mode = (
        StrategyExecutionMode.CHAMPION_ONLY
        if StrategyExecutionMode.CHAMPION_ONLY
        in (system.strategy_execution_mode, campaign.strategy_execution_mode)
        else StrategyExecutionMode.ISOLATED_CHALLENGER_PAPER
    )
    mode_source = (
        ConstraintSource.SYSTEM
        if system.strategy_execution_mode is StrategyExecutionMode.CHAMPION_ONLY
        else ConstraintSource.CAMPAIGN
    )
    effective = EffectiveConstraintSet(
        maximum_loss_per_trade=maximum_loss,
        maximum_campaign_loss=maximum_campaign_loss,
        drawdown_limit=drawdown,
        max_trades=max_trades,
        max_concurrent_positions=concurrency,
        capital_budget=capital,
        maximum_budget_per_trade=budget_per_trade,
        minimum_calibrated_probability=probability,
        minimum_calibration_support=support,
        minimum_expected_edge_r=edge,
        minimum_reward_risk=reward_risk,
        allowed_instruments=instruments,
        allowed_timeframes=timeframes,
        allowed_strategies=strategies,
        strategy_execution_mode=mode,
    )
    selections = {
        ConstraintCode.MAXIMUM_LOSS_PER_TRADE: (maximum_loss, loss_source),
        ConstraintCode.MAXIMUM_CAMPAIGN_LOSS: (maximum_campaign_loss, campaign_loss_source),
        ConstraintCode.DRAWDOWN_LIMIT: (drawdown, drawdown_source),
        ConstraintCode.MAX_TRADES: (max_trades, max_trades_source),
        ConstraintCode.MAX_CONCURRENT_POSITIONS: (concurrency, concurrency_source),
        ConstraintCode.CAPITAL_BUDGET: (capital, capital_source),
        ConstraintCode.MAXIMUM_BUDGET_PER_TRADE: (budget_per_trade, budget_source),
        ConstraintCode.MINIMUM_CALIBRATED_PROBABILITY: (probability, probability_source),
        ConstraintCode.MINIMUM_CALIBRATION_SUPPORT: (support, support_source),
        ConstraintCode.MINIMUM_EXPECTED_EDGE_R: (edge, edge_source),
        ConstraintCode.MINIMUM_REWARD_RISK: (reward_risk, reward_source),
        ConstraintCode.ALLOWED_INSTRUMENTS: (instruments, ConstraintSource.CAMPAIGN),
        ConstraintCode.ALLOWED_TIMEFRAMES: (timeframes, ConstraintSource.CAMPAIGN),
        ConstraintCode.ALLOWED_STRATEGIES: (strategies, ConstraintSource.CAMPAIGN),
        ConstraintCode.STRATEGY_EXECUTION_MODE: (mode, mode_source),
    }
    provenance = tuple(
        ConstraintProvenance(
            constraint_code=code,
            winning_source=selections[code][1],
            source_refs=refs,
            selected_value=canonicalize(selections[code][0]),
        )
        for code in ConstraintCode
    )
    return ConstraintComposition(effective=effective, provenance=provenance)


__all__ = ["compose_constraints", "resolve_authority_value"]
