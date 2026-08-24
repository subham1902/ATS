"""Internal immutable inputs and results for the deterministic A04 kernel."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import model_validator

from ats.contracts.common import ATSBaseModel, Probability
from ats.contracts.domain.types import (
    InstrumentId,
    MoneyOrPortfolioFraction,
    NonNegativeDecimal,
    PaperOrderType,
    PortfolioFraction,
    PositiveDecimal,
    PositiveInt,
    Sha256,
    Side,
    ensure_unique,
)
from ats.contracts.enums import ATSStringEnum
from ats.contracts.governance.types import (
    ConstraintProvenance,
    EffectiveConstraintSet,
    RiskDirection,
    StrategyExecutionMode,
)
from ats.contracts.intelligence.types import PositiveFiniteFloat, RegisteredCode, StrategyRef


class KernelOutcome(ATSStringEnum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    UNKNOWN = "UNKNOWN"


class GateCode(ATSStringEnum):
    OK = "OK"
    POLICY_INACTIVE = "POLICY_INACTIVE"
    AUTONOMY_NOT_A2 = "AUTONOMY_NOT_A2"
    POLICY_TIME_INVALID = "POLICY_TIME_INVALID"
    POLICY_INCOMPATIBLE = "POLICY_INCOMPATIBLE"
    LOSS_STATE_NON_MONOTONIC = "LOSS_STATE_NON_MONOTONIC"
    EMPTY_INTERSECTION = "EMPTY_INTERSECTION"
    ACTION_RISK_MISMATCH = "ACTION_RISK_MISMATCH"
    ACTION_RISK_UNKNOWN = "ACTION_RISK_UNKNOWN"
    SYSTEM_STATE_DENY = "SYSTEM_STATE_DENY"
    EXECUTION_STATE_UNSAFE = "EXECUTION_STATE_UNSAFE"
    CAMPAIGN_INACTIVE = "CAMPAIGN_INACTIVE"
    CAMPAIGN_TIME_INVALID = "CAMPAIGN_TIME_INVALID"
    CAMPAIGN_LIMIT_REACHED = "CAMPAIGN_LIMIT_REACHED"
    CAMPAIGN_COOLDOWN = "CAMPAIGN_COOLDOWN"
    CAMPAIGN_BINDING_MISMATCH = "CAMPAIGN_BINDING_MISMATCH"
    DATA_STALE = "DATA_STALE"
    DATA_QUALITY = "DATA_QUALITY"
    EVIDENCE_EXPIRED = "EVIDENCE_EXPIRED"
    EVIDENCE_BINDING_MISMATCH = "EVIDENCE_BINDING_MISMATCH"
    CALIBRATION_SUPPORT = "CALIBRATION_SUPPORT"
    PROBABILITY_THRESHOLD = "PROBABILITY_THRESHOLD"
    PROBABILITY_BINDING = "PROBABILITY_BINDING"
    EDGE_THRESHOLD = "EDGE_THRESHOLD"
    REWARD_RISK_THRESHOLD = "REWARD_RISK_THRESHOLD"
    STRATEGY_STATUS = "STRATEGY_STATUS"
    CANDIDATE_BINDING = "CANDIDATE_BINDING"
    RISK_DENY = "RISK_DENY"
    RISK_UNKNOWN = "RISK_UNKNOWN"
    ADVISORY_DENY = "ADVISORY_DENY"
    TOKEN_TTL = "TOKEN_TTL"
    TOKEN_INVALID = "TOKEN_INVALID"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"
    TOKEN_CONSUMED = "TOKEN_CONSUMED"
    TOKEN_STALE_STATE = "TOKEN_STALE_STATE"
    ORDER_BINDING = "ORDER_BINDING"
    ORDER_TYPE = "ORDER_TYPE"
    NOTIONAL_MISMATCH = "NOTIONAL_MISMATCH"
    LOSS_LIMIT = "LOSS_LIMIT"
    BUDGET_LIMIT = "BUDGET_LIMIT"
    ECONOMICS_INVALID = "ECONOMICS_INVALID"
    POSITION_BINDING = "POSITION_BINDING"
    QUANTITY_INVALID = "QUANTITY_INVALID"
    UNRESOLVED_BASIS = "UNRESOLVED_BASIS"


class KernelResult(ATSBaseModel):
    outcome: KernelOutcome
    reason_codes: tuple[GateCode, ...]

    @model_validator(mode="after")
    def validate_reasons(self) -> KernelResult:
        ensure_unique(self.reason_codes, "reason_codes")
        if self.outcome is KernelOutcome.ALLOW and self.reason_codes != (GateCode.OK,):
            raise ValueError("ALLOW must contain only OK")
        if self.outcome is not KernelOutcome.ALLOW and not self.reason_codes:
            raise ValueError("DENY/UNKNOWN require reasons")
        return self


ALLOW = KernelResult(outcome=KernelOutcome.ALLOW, reason_codes=(GateCode.OK,))


class SystemConstraintSet(ATSBaseModel):
    constraint_set_id: UUID
    constraint_set_version: PositiveInt
    maximum_loss_per_trade: MoneyOrPortfolioFraction
    maximum_campaign_loss: MoneyOrPortfolioFraction
    drawdown_limit: PortfolioFraction
    max_trades: PositiveInt
    max_concurrent_positions: PositiveInt
    capital_budget: PositiveDecimal
    maximum_budget_per_trade: MoneyOrPortfolioFraction
    minimum_calibrated_probability: Probability
    minimum_calibration_support: PositiveInt
    minimum_expected_edge_r: PositiveFiniteFloat
    minimum_reward_risk: PositiveDecimal
    allowed_instruments: tuple[InstrumentId, ...]
    allowed_timeframes: tuple[RegisteredCode, ...]
    allowed_strategies: tuple[StrategyRef, ...]
    strategy_execution_mode: StrategyExecutionMode

    @model_validator(mode="after")
    def validate_allowlists(self) -> SystemConstraintSet:
        for name in ("allowed_instruments", "allowed_timeframes", "allowed_strategies"):
            values = getattr(self, name)
            if not values:
                raise ValueError(f"{name} must be non-empty")
            ensure_unique(values, name)
        return self


class ConstraintComposition(ATSBaseModel):
    effective: EffectiveConstraintSet
    provenance: tuple[ConstraintProvenance, ...]


class ProtectionChange(ATSStringEnum):
    TIGHTENED = "TIGHTENED"
    UNCHANGED = "UNCHANGED"
    LOOSENED = "LOOSENED"
    REMOVED = "REMOVED"
    UNKNOWN = "UNKNOWN"


class RiskClassificationStatus(ATSStringEnum):
    CLASSIFIED = "CLASSIFIED"
    UNKNOWN = "UNKNOWN"


class RiskClassification(ATSBaseModel):
    status: RiskClassificationStatus
    direction: RiskDirection | None
    protection_change: ProtectionChange | None
    reason_codes: tuple[GateCode, ...]


class ProtectiveExitChangeFacts(ATSBaseModel):
    position_side: Side
    current_protective_price: PositiveDecimal | None
    proposed_protective_price: PositiveDecimal | None
    current_protected_quantity: NonNegativeDecimal
    proposed_protected_quantity: NonNegativeDecimal


class OrderSemanticRole(ATSStringEnum):
    ENTRY = "ENTRY"
    POSITION_INCREASE = "POSITION_INCREASE"
    PROTECTIVE_EXIT = "PROTECTIVE_EXIT"
    POSITION_REDUCTION = "POSITION_REDUCTION"
    OTHER = "OTHER"
    UNKNOWN = "UNKNOWN"


class CancelOrderFacts(ATSBaseModel):
    role: OrderSemanticRole


class ExecutionSafetyFacts(ATSBaseModel):
    position_state_known: bool
    execution_state_known: bool
    position_ownership_known: bool
    ambiguous_exit_pending: bool
    reconciliation_mismatch: bool

    @property
    def fully_known_safe(self) -> bool:
        return (
            self.position_state_known
            and self.execution_state_known
            and self.position_ownership_known
            and not self.ambiguous_exit_pending
            and not self.reconciliation_mismatch
        )


class RiskCapitalBasis(ATSBaseModel):
    portfolio_equity: PositiveDecimal
    campaign_equity_basis: PositiveDecimal


class CampaignEvaluationFacts(ATSBaseModel):
    stop_condition_triggered: bool
    campaign_loss_limit_reached: bool
    capital_limit_reached: bool


class AutonomyTokenPolicy(ATSBaseModel):
    max_ttl_ms: PositiveInt


class DecisionBindingEvidence(ATSBaseModel):
    candidate_id: UUID
    candidate_version: PositiveInt
    candidate_payload_hash: Sha256
    governance_context_id: UUID
    governance_context_hash: Sha256
    campaign_id: UUID
    campaign_version: PositiveInt
    market_thesis_id: UUID
    market_thesis_version: PositiveInt
    distribution_id: UUID
    strategy_definition_id: UUID
    strategy_definition_version: PositiveInt


class OrderGuardPolicy(ATSBaseModel):
    allowed_order_types: tuple[PaperOrderType, ...]

    @model_validator(mode="after")
    def validate_types(self) -> OrderGuardPolicy:
        if not self.allowed_order_types:
            raise ValueError("allowed_order_types must be non-empty")
        ensure_unique(self.allowed_order_types, "allowed_order_types")
        return self


class OrderEvaluationFacts(ATSBaseModel):
    reference_price: PositiveDecimal
    contract_multiplier: PositiveDecimal
    estimated_fees: NonNegativeDecimal
    estimated_slippage: NonNegativeDecimal
    estimated_notional: PositiveDecimal
    estimated_maximum_loss: PositiveDecimal
    estimated_expected_reward: NonNegativeDecimal


class ExitEvaluationFacts(ATSBaseModel):
    reducible_quantity: PositiveDecimal


AuthorityScope = Literal["A2_PAPER"]


__all__ = [name for name in globals() if not name.startswith("_")]
