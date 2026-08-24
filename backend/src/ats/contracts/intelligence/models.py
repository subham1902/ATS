"""Frozen IBA-C01 intelligence contracts: immutable data and intrinsic validation only."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import model_validator

from ats.contracts.common import ATSBaseModel, FiniteDecimal, FiniteFloat, Probability, UTCDateTime
from ats.contracts.domain.types import (
    DataQualityState,
    ForecastStatus,
    InstrumentId,
    NonEmptyStr,
    NonNegativeDecimal,
    NonNegativeInt,
    PortfolioFraction,
    PositiveDecimal,
    PositiveInt,
    Predicate,
    SessionState,
    Sha256,
    UnitIntervalFloat,
    ensure_unique,
)

from .types import (
    AnalogueMatch,
    AnalogueOutcomeStat,
    AnalystVerdict,
    ApprovalMode,
    AssetClass,
    AttributionComponent,
    AttributionScope,
    BoundedText,
    CalibratedOutcome,
    EnsembleMember,
    ExperimentStatus,
    ExperimentType,
    ExplanationAnswerability,
    ExplanationFact,
    FormulaNode,
    FormulaNodeKind,
    FormulaOutputKind,
    FormulaPurpose,
    GuidelineProposal,
    LeakageScanStatus,
    LiquidityState,
    MarketThesisStatus,
    NonNegativeFiniteFloat,
    OutcomeProbability,
    PriceLevel,
    PromotionOutcome,
    RegimeConstraint,
    RegimeDirection,
    RegimeStructure,
    RegisteredCode,
    ScorecardValidationStatus,
    Shortability,
    StrategyOrigin,
    StrategyParameter,
    StrategyRef,
    StrategyStatus,
    ThesisStance,
    VersionedRef,
    VolatilityState,
)

UNIT_SUM_TOLERANCE = 1e-9


class InstrumentSpec(ATSBaseModel):
    schema_version: Literal["1.0"]
    instrument_spec_id: UUID
    instrument_spec_version: PositiveInt
    instrument_id: InstrumentId
    asset_class: AssetClass
    venue: NonEmptyStr
    symbol: NonEmptyStr
    base_asset: RegisteredCode | None
    quote_currency: RegisteredCode
    settlement_currency: RegisteredCode
    tick_size: PositiveDecimal
    quantity_step: PositiveDecimal
    minimum_quantity: PositiveDecimal
    contract_multiplier: PositiveDecimal
    timezone: NonEmptyStr
    session_calendar_id: RegisteredCode
    trading_hours_profile: RegisteredCode
    shortability: Shortability
    leverage_allowed: bool
    maximum_leverage: PositiveDecimal | None
    fee_model_id: RegisteredCode
    funding_model_id: RegisteredCode | None
    corporate_action_policy_id: RegisteredCode | None
    supported_timeframes: tuple[RegisteredCode, ...]
    effective_from: UTCDateTime
    effective_until: UTCDateTime | None
    source: NonEmptyStr
    source_version: NonEmptyStr
    payload_hash: Sha256

    @model_validator(mode="after")
    def validate_spec(self) -> InstrumentSpec:
        if not self.supported_timeframes:
            raise ValueError("supported_timeframes must be non-empty")
        ensure_unique(self.supported_timeframes, "supported_timeframes")
        if self.leverage_allowed != (self.maximum_leverage is not None):
            raise ValueError("maximum_leverage presence must match leverage_allowed")
        if self.maximum_leverage is not None and self.maximum_leverage < Decimal(1):
            raise ValueError("maximum_leverage must be >= 1")
        if self.effective_until is not None and self.effective_until <= self.effective_from:
            raise ValueError("effective_until must be > effective_from")
        if (
            self.asset_class in (AssetClass.FOREX, AssetClass.CRYPTO, AssetClass.FUTURE)
            and self.base_asset is None
        ):
            raise ValueError("base_asset is required for this asset class")
        return self


class MarketContext(ATSBaseModel):
    schema_version: Literal["1.0"]
    market_context_id: UUID
    instrument_spec_id: UUID
    instrument_id: InstrumentId
    snapshot_id: UUID
    feature_bundle_id: UUID
    timeframe: RegisteredCode
    as_of_time: UTCDateTime
    data_cutoff: UTCDateTime
    session_state: SessionState
    data_quality_state: DataQualityState
    freshness_ms: NonNegativeInt
    liquidity_state: LiquidityState
    volatility_state: VolatilityState
    higher_timeframe_context_refs: tuple[UUID, ...]
    related_market_context_refs: tuple[UUID, ...]
    cost_model_version: NonEmptyStr
    input_hash: Sha256
    payload_hash: Sha256

    @model_validator(mode="after")
    def validate_context(self) -> MarketContext:
        if self.data_cutoff > self.as_of_time:
            raise ValueError("data_cutoff must be <= as_of_time")
        ensure_unique(self.higher_timeframe_context_refs, "higher_timeframe_context_refs")
        ensure_unique(self.related_market_context_refs, "related_market_context_refs")
        return self


class RegimeEvidence(ATSBaseModel):
    schema_version: Literal["1.0"]
    regime_evidence_id: UUID
    market_context_id: UUID
    instrument_id: InstrumentId
    timeframe: RegisteredCode
    as_of_time: UTCDateTime
    data_cutoff: UTCDateTime
    detector_id: NonEmptyStr
    detector_version: NonEmptyStr
    direction: RegimeDirection
    structure: RegimeStructure
    volatility: VolatilityState
    liquidity: LiquidityState
    change_score: UnitIntervalFloat
    regime_familiarity: UnitIntervalFloat
    support_window_bars: PositiveInt
    reason_codes: tuple[RegisteredCode, ...]
    quality_state: DataQualityState
    payload_hash: Sha256

    @model_validator(mode="after")
    def validate_evidence(self) -> RegimeEvidence:
        if self.data_cutoff > self.as_of_time:
            raise ValueError("data_cutoff must be <= as_of_time")
        ensure_unique(self.reason_codes, "reason_codes")
        return self


class AnalogueEvidence(ATSBaseModel):
    schema_version: Literal["1.0"]
    analogue_evidence_id: UUID
    market_context_id: UUID
    instrument_id: InstrumentId
    timeframe: RegisteredCode
    query_window_start: UTCDateTime
    query_window_end: UTCDateTime
    as_of_time: UTCDateTime
    data_cutoff: UTCDateTime
    retrieval_method: RegisteredCode
    retrieval_version: NonEmptyStr
    corpus_id: UUID
    corpus_version: NonEmptyStr
    corpus_cutoff: UTCDateTime
    requested_top_k: PositiveInt
    matches: tuple[AnalogueMatch, ...]
    event_definition_id: UUID
    forward_horizon_bars: PositiveInt
    outcome_summary: tuple[AnalogueOutcomeStat, ...]
    leakage_check_passed: Literal[True]
    quality_state: DataQualityState
    payload_hash: Sha256

    @model_validator(mode="after")
    def validate_analogue(self) -> AnalogueEvidence:
        if (
            not self.query_window_start
            <= self.query_window_end
            <= self.data_cutoff
            <= self.as_of_time
        ):
            raise ValueError("invalid query/data cutoff ordering")
        if self.corpus_cutoff > self.data_cutoff:
            raise ValueError("corpus_cutoff must be <= data_cutoff")
        if len(self.matches) > self.requested_top_k or any(
            match.window_end > self.corpus_cutoff for match in self.matches
        ):
            raise ValueError("analogue match violates top-k or corpus cutoff")
        ensure_unique(tuple(match.analogue_id for match in self.matches), "match analogue IDs")
        ensure_unique(tuple(item.outcome_code for item in self.outcome_summary), "outcome codes")
        return self


class EnsembleForecast(ATSBaseModel):
    schema_version: Literal["1.0"]
    ensemble_forecast_id: UUID
    market_context_id: UUID
    instrument_id: InstrumentId
    timeframe: RegisteredCode
    event_definition_id: UUID
    horizon_bars: PositiveInt
    as_of_time: UTCDateTime
    data_cutoff: UTCDateTime
    aggregation_method: RegisteredCode
    aggregation_version: NonEmptyStr
    members: tuple[EnsembleMember, ...]
    raw_outcomes: tuple[OutcomeProbability, ...]
    disagreement_score: UnitIntervalFloat
    effective_member_count: NonNegativeInt
    baseline_member_ids: tuple[UUID, ...]
    status: ForecastStatus
    payload_hash: Sha256

    @model_validator(mode="after")
    def validate_ensemble(self) -> EnsembleForecast:
        if self.data_cutoff > self.as_of_time:
            raise ValueError("data_cutoff must be <= as_of_time")
        ensure_unique(tuple(item.forecast_id for item in self.members), "member forecast IDs")
        ensure_unique(tuple(item.outcome_code for item in self.raw_outcomes), "outcome codes")
        ensure_unique(self.baseline_member_ids, "baseline_member_ids")
        if self.effective_member_count != sum(item.weight > 0 for item in self.members):
            raise ValueError("effective_member_count mismatch")
        if self.status in (ForecastStatus.READY, ForecastStatus.DEGRADED):
            if not self.members or not self.raw_outcomes:
                raise ValueError("ready/degraded ensemble requires members and outcomes")
            if abs(sum(item.weight for item in self.members) - 1.0) > UNIT_SUM_TOLERANCE:
                raise ValueError("member weights must sum to one")
            if abs(
                sum((item.probability for item in self.raw_outcomes), Decimal(0)) - Decimal(1)
            ) > Decimal("1e-9"):
                raise ValueError("outcome probabilities must sum to one")
        return self


class CalibratedOutcomeDistribution(ATSBaseModel):
    schema_version: Literal["1.0"]
    distribution_id: UUID
    ensemble_forecast_id: UUID
    market_context_id: UUID
    instrument_id: InstrumentId
    event_definition_id: UUID
    horizon_bars: PositiveInt
    as_of_time: UTCDateTime
    data_cutoff: UTCDateTime
    calibrator_id: RegisteredCode
    calibrator_version: NonEmptyStr
    calibration_window_start: UTCDateTime
    calibration_window_end: UTCDateTime
    support_count: NonNegativeInt
    outcomes: tuple[CalibratedOutcome, ...]
    brier_score: UnitIntervalFloat
    expected_calibration_error: UnitIntervalFloat
    regime_conditioned: bool
    regime_evidence_id: UUID | None
    expected_return_fraction: FiniteFloat
    expected_volatility_fraction: NonNegativeFiniteFloat
    expected_mfe_fraction: FiniteFloat
    expected_mae_fraction: FiniteFloat
    tail_loss_probability: Probability
    quality_state: DataQualityState
    valid_until: UTCDateTime
    payload_hash: Sha256

    @model_validator(mode="after")
    def validate_distribution(self) -> CalibratedOutcomeDistribution:
        if (
            not self.calibration_window_start
            <= self.calibration_window_end
            <= self.data_cutoff
            <= self.as_of_time
        ):
            raise ValueError("invalid calibration/data cutoff ordering")
        if self.valid_until <= self.as_of_time:
            raise ValueError("valid_until must be > as_of_time")
        ensure_unique(tuple(item.outcome_code for item in self.outcomes), "outcome codes")
        if abs(
            sum((item.probability for item in self.outcomes), Decimal(0)) - Decimal(1)
        ) > Decimal("1e-9"):
            raise ValueError("calibrated probabilities must sum to one")
        if self.regime_conditioned != (self.regime_evidence_id is not None):
            raise ValueError("regime evidence presence must match regime_conditioned")
        return self


class MarketThesis(ATSBaseModel):
    schema_version: Literal["1.0"]
    thesis_id: UUID
    thesis_version: PositiveInt
    instrument_id: InstrumentId
    market_context_id: UUID
    regime_evidence_id: UUID
    analogue_evidence_id: UUID | None
    ensemble_forecast_id: UUID
    distribution_id: UUID
    timeframe: RegisteredCode
    as_of_time: UTCDateTime
    data_cutoff: UTCDateTime
    stance: ThesisStance
    thesis_strength: UnitIntervalFloat
    support_levels: tuple[PriceLevel, ...]
    resistance_levels: tuple[PriceLevel, ...]
    opportunity_conditions: tuple[Predicate, ...]
    invalidation_conditions: tuple[Predicate, ...]
    disagreement_score: UnitIntervalFloat
    evidence_refs: tuple[UUID, ...]
    data_quality_state: DataQualityState
    expires_at: UTCDateTime
    status: MarketThesisStatus
    supersedes_version: PositiveInt | None
    invalidation_reason_codes: tuple[RegisteredCode, ...]
    payload_hash: Sha256

    @model_validator(mode="after")
    def validate_thesis(self) -> MarketThesis:
        if self.data_cutoff > self.as_of_time:
            raise ValueError("data_cutoff must be <= as_of_time")
        if self.status is MarketThesisStatus.ACTIVE and self.expires_at <= self.as_of_time:
            raise ValueError("ACTIVE thesis must expire after as_of_time")
        if self.status is MarketThesisStatus.INVALIDATED and not self.invalidation_reason_codes:
            raise ValueError("INVALIDATED thesis requires reasons")
        expected = None if self.thesis_version == 1 else self.thesis_version - 1
        if self.supersedes_version != expected:
            raise ValueError("supersedes_version must reference the previous version")
        ensure_unique(self.evidence_refs, "evidence_refs")
        ensure_unique(self.invalidation_reason_codes, "invalidation_reason_codes")
        return self


class AnalystAssessment(ATSBaseModel):
    schema_version: Literal["1.0"]
    assessment_id: UUID
    thesis_id: UUID
    thesis_version: PositiveInt
    model_id: NonEmptyStr
    model_version: NonEmptyStr
    verdict: AnalystVerdict
    quoted_distribution_id: UUID
    reason_codes: tuple[RegisteredCode, ...]
    uncertainty_flags: tuple[RegisteredCode, ...]
    rationale: BoundedText
    proposed_guidelines: tuple[GuidelineProposal, ...]
    evidence_refs: tuple[UUID, ...]
    created_at: UTCDateTime
    payload_hash: Sha256


class StrategyDefinition(ATSBaseModel):
    schema_version: Literal["1.0"]
    strategy_definition_id: UUID
    strategy_definition_version: PositiveInt
    name: NonEmptyStr
    strategy_family: RegisteredCode
    status: StrategyStatus
    feature_formula_refs: tuple[VersionedRef, ...]
    entry_formula_ref: VersionedRef
    exit_formula_refs: tuple[VersionedRef, ...]
    compatible_asset_classes: tuple[AssetClass, ...]
    compatible_venues: tuple[RegisteredCode, ...]
    compatible_instruments: tuple[InstrumentId, ...]
    compatible_timeframes: tuple[RegisteredCode, ...]
    required_features: tuple[RegisteredCode, ...]
    required_model_families: tuple[RegisteredCode, ...]
    regime_constraints: tuple[RegimeConstraint, ...]
    parameters: tuple[StrategyParameter, ...]
    origin: StrategyOrigin
    parent_strategy_ref: StrategyRef | None
    source_instruction_hash: Sha256
    validation_report_hash: Sha256
    created_at: UTCDateTime
    payload_hash: Sha256

    @model_validator(mode="after")
    def validate_definition(self) -> StrategyDefinition:
        if not self.compatible_asset_classes or not self.compatible_timeframes:
            raise ValueError("asset classes and timeframes must be non-empty")
        for name in (
            "feature_formula_refs",
            "exit_formula_refs",
            "compatible_asset_classes",
            "compatible_venues",
            "compatible_instruments",
            "compatible_timeframes",
            "required_features",
            "required_model_families",
            "regime_constraints",
        ):
            ensure_unique(getattr(self, name), name)
        ensure_unique(tuple(item.parameter_code for item in self.parameters), "parameter codes")
        return self


def _ast_metadata(node: FormulaNode) -> tuple[int, int, int, set[str]]:
    child = [_ast_metadata(item) for item in node.arguments]
    depth = 1 + max((item[0] for item in child), default=0)
    count = 1 + sum(item[1] for item in child)
    lag = max([node.lag_bars or 0, *(item[2] for item in child)])
    features = set().union(*(item[3] for item in child)) if child else set()
    if node.node_kind is FormulaNodeKind.FEATURE and node.feature_code is not None:
        features.add(node.feature_code)
    return depth, count, lag, features


class FormulaDefinition(ATSBaseModel):
    schema_version: Literal["1.0"]
    formula_definition_id: UUID
    formula_version: PositiveInt
    name: NonEmptyStr
    purpose: FormulaPurpose
    output_kind: FormulaOutputKind
    timeframe: RegisteredCode
    lookback_bars: NonNegativeInt
    warmup_bars: NonNegativeInt
    ast: FormulaNode
    ast_depth: PositiveInt
    node_count: PositiveInt
    max_lag_bars: NonNegativeInt
    required_features: tuple[RegisteredCode, ...]
    parameters: tuple[StrategyParameter, ...]
    source_instruction_hash: Sha256
    origin: StrategyOrigin
    created_at: UTCDateTime
    payload_hash: Sha256

    @model_validator(mode="after")
    def validate_formula(self) -> FormulaDefinition:
        depth, count, lag, features = _ast_metadata(self.ast)
        if (self.ast_depth, self.node_count, self.max_lag_bars) != (depth, count, lag):
            raise ValueError("AST metadata mismatch")
        ensure_unique(self.required_features, "required_features")
        if set(self.required_features) != features:
            raise ValueError("required_features mismatch")
        if self.lookback_bars < self.max_lag_bars or self.lookback_bars < self.warmup_bars:
            raise ValueError("lookback_bars is too small")
        ensure_unique(tuple(item.parameter_code for item in self.parameters), "parameter codes")
        if (
            self.purpose in (FormulaPurpose.ENTRY_FILTER, FormulaPurpose.EXIT_FILTER)
            and self.output_kind is not FormulaOutputKind.BOOLEAN
        ):
            raise ValueError("entry/exit filters require BOOLEAN output")
        if (
            self.purpose is FormulaPurpose.PRICE_LEVEL
            and self.output_kind is not FormulaOutputKind.DECIMAL
        ):
            raise ValueError("price levels require DECIMAL output")
        if self.purpose is FormulaPurpose.SCORE and self.output_kind not in (
            FormulaOutputKind.FINITE_FLOAT,
            FormulaOutputKind.DECIMAL,
        ):
            raise ValueError("scores require numeric output")
        return self


class StrategyExperiment(ATSBaseModel):
    schema_version: Literal["1.0"]
    experiment_id: UUID
    strategy_definition_id: UUID
    strategy_definition_version: PositiveInt
    experiment_type: ExperimentType
    status: ExperimentStatus
    instrument_universe: tuple[InstrumentId, ...]
    timeframe: RegisteredCode
    dataset_manifest_id: UUID
    dataset_version: NonEmptyStr
    dataset_cutoff: UTCDateTime
    train_start: UTCDateTime | None
    train_end: UTCDateTime | None
    test_start: UTCDateTime
    test_end: UTCDateTime | None
    purge_bars: NonNegativeInt
    embargo_bars: NonNegativeInt
    cost_model_version: NonEmptyStr
    parameter_set_hash: Sha256
    seed: int
    benchmark_strategy_refs: tuple[StrategyRef, ...]
    leakage_scan_status: LeakageScanStatus
    shadow_campaign_id: UUID | None
    started_at: UTCDateTime | None
    completed_at: UTCDateTime | None
    scorecard_id: UUID | None
    reason_codes: tuple[RegisteredCode, ...]
    payload_hash: Sha256

    @model_validator(mode="after")
    def validate_experiment(self) -> StrategyExperiment:
        if not self.instrument_universe:
            raise ValueError("instrument_universe must be non-empty")
        ensure_unique(self.instrument_universe, "instrument_universe")
        ensure_unique(self.benchmark_strategy_refs, "benchmark_strategy_refs")
        if (self.train_start is None) != (self.train_end is None):
            raise ValueError("training range must be all-or-none")
        if (
            self.train_start is not None
            and self.train_end is not None
            and not self.train_start < self.train_end <= self.test_start
        ):
            raise ValueError("invalid training range")
        if self.test_end is not None and not self.test_start < self.test_end <= self.dataset_cutoff:
            raise ValueError("invalid test range")
        if (self.experiment_type is ExperimentType.SHADOW_PAPER) != (
            self.shadow_campaign_id is not None
        ):
            raise ValueError("shadow campaign presence must match SHADOW_PAPER")
        if self.status is ExperimentStatus.PLANNED and any(
            v is not None for v in (self.started_at, self.completed_at, self.scorecard_id)
        ):
            raise ValueError("invalid PLANNED timestamps")
        if self.status is ExperimentStatus.RUNNING and (
            self.started_at is None
            or self.completed_at is not None
            or self.scorecard_id is not None
        ):
            raise ValueError("invalid RUNNING timestamps")
        if self.status is ExperimentStatus.COMPLETED and (
            self.started_at is None
            or self.completed_at is None
            or self.test_end is None
            or self.scorecard_id is None
            or self.leakage_scan_status is not LeakageScanStatus.PASS
        ):
            raise ValueError("invalid COMPLETED evidence")
        if self.status in (ExperimentStatus.FAILED, ExperimentStatus.INVALIDATED) and (
            self.started_at is None or self.completed_at is None
        ):
            raise ValueError("terminal run requires timestamps")
        if self.status is ExperimentStatus.CANCELLED and self.completed_at is None:
            raise ValueError("CANCELLED requires completed_at")
        return self


class StrategyScorecard(ATSBaseModel):
    schema_version: Literal["1.0"]
    scorecard_id: UUID
    strategy_definition_id: UUID
    strategy_definition_version: PositiveInt
    experiment_ids: tuple[UUID, ...]
    evaluation_start: UTCDateTime
    evaluation_end: UTCDateTime
    sample_count: NonNegativeInt
    trade_count: NonNegativeInt
    net_return_fraction: FiniteFloat
    expectancy_r: FiniteFloat
    profit_factor: NonNegativeFiniteFloat | None
    win_rate: Probability | None
    average_win_r: FiniteFloat | None
    average_loss_r: FiniteFloat | None
    maximum_drawdown: PortfolioFraction
    sharpe: FiniteFloat | None
    sortino: FiniteFloat | None
    tail_loss_metric: NonNegativeFiniteFloat
    turnover: NonNegativeFiniteFloat
    estimated_costs: NonNegativeDecimal
    stability_score: UnitIntervalFloat
    parameter_sensitivity_score: UnitIntervalFloat
    regime_coverage_score: UnitIntervalFloat
    benchmark_delta: FiniteFloat
    validation_status: ScorecardValidationStatus
    created_at: UTCDateTime
    payload_hash: Sha256

    @model_validator(mode="after")
    def validate_scorecard(self) -> StrategyScorecard:
        if not self.experiment_ids:
            raise ValueError("experiment_ids must be non-empty")
        ensure_unique(self.experiment_ids, "experiment_ids")
        if self.evaluation_end < self.evaluation_start:
            raise ValueError("evaluation_end must be >= evaluation_start")
        if self.trade_count == 0 and any(
            v is not None for v in (self.win_rate, self.average_win_r, self.average_loss_r)
        ):
            raise ValueError("zero trades cannot have win statistics")
        return self


class PromotionDecision(ATSBaseModel):
    schema_version: Literal["1.0"]
    promotion_decision_id: UUID
    candidate_strategy_ref: StrategyRef
    incumbent_strategy_ref: StrategyRef | None
    scorecard_ids: tuple[UUID, ...]
    decision: PromotionOutcome
    target_status: Literal["CHAMPION"]
    approval_mode: ApprovalMode
    required_gates_passed: bool
    minimum_evidence_met: bool
    risk_constraints_unchanged: Literal[True]
    approved_by: NonEmptyStr | None
    approved_at: UTCDateTime | None
    effective_from: UTCDateTime | None
    reason_codes: tuple[RegisteredCode, ...]
    decided_at: UTCDateTime
    payload_hash: Sha256

    @model_validator(mode="after")
    def validate_promotion(self) -> PromotionDecision:
        if not self.scorecard_ids:
            raise ValueError("scorecard_ids must be non-empty")
        ensure_unique(self.scorecard_ids, "scorecard_ids")
        if self.decision is PromotionOutcome.PROMOTE:
            if (
                not self.required_gates_passed
                or not self.minimum_evidence_met
                or self.effective_from is None
                or self.effective_from < self.decided_at
            ):
                raise ValueError("PROMOTE requirements not met")
            if self.approval_mode is ApprovalMode.HUMAN and (
                self.approved_by is None or self.approved_at is None
            ):
                raise ValueError("HUMAN promotion requires approval")
        elif self.effective_from is not None:
            raise ValueError("REJECT/DEFER cannot have effective_from")
        return self


class PerformanceAttribution(ATSBaseModel):
    schema_version: Literal["1.0"]
    attribution_id: UUID
    scope_type: AttributionScope
    scope_id: UUID
    window_start: UTCDateTime
    window_end: UTCDateTime
    as_of_time: UTCDateTime
    data_cutoff: UTCDateTime
    method_id: RegisteredCode
    method_version: NonEmptyStr
    observed_pnl: FiniteDecimal
    components: tuple[AttributionComponent, ...]
    unattributed_residual: FiniteDecimal
    counterfactual_refs: tuple[UUID, ...]
    evidence_refs: tuple[UUID, ...]
    quality_state: DataQualityState
    created_at: UTCDateTime
    payload_hash: Sha256

    @model_validator(mode="after")
    def validate_attribution(self) -> PerformanceAttribution:
        if not self.window_start <= self.window_end <= self.data_cutoff <= self.as_of_time:
            raise ValueError("invalid attribution time ordering")
        ensure_unique(self.counterfactual_refs, "counterfactual_refs")
        ensure_unique(self.evidence_refs, "evidence_refs")
        return self


class ExplanationEvidence(ATSBaseModel):
    schema_version: Literal["1.0"]
    explanation_evidence_id: UUID
    query_hash: Sha256
    intent: Literal["QUESTION"]
    scope_refs: tuple[UUID, ...]
    as_of_time: UTCDateTime
    data_cutoff: UTCDateTime
    causal_event_refs: tuple[UUID, ...]
    decision_refs: tuple[UUID, ...]
    market_evidence_refs: tuple[UUID, ...]
    performance_attribution_refs: tuple[UUID, ...]
    facts: tuple[ExplanationFact, ...]
    missing_information: tuple[NonEmptyStr, ...]
    answerability: ExplanationAnswerability
    created_at: UTCDateTime
    payload_hash: Sha256

    @model_validator(mode="after")
    def validate_explanation(self) -> ExplanationEvidence:
        if self.data_cutoff > self.as_of_time:
            raise ValueError("data_cutoff must be <= as_of_time")
        for name in (
            "scope_refs",
            "causal_event_refs",
            "decision_refs",
            "market_evidence_refs",
            "performance_attribution_refs",
        ):
            ensure_unique(getattr(self, name), name)
        if self.answerability is ExplanationAnswerability.FULL and (
            not self.facts or self.missing_information
        ):
            raise ValueError("FULL requires facts and no missing information")
        if self.answerability is ExplanationAnswerability.PARTIAL and (
            not self.facts or not self.missing_information
        ):
            raise ValueError("PARTIAL requires facts and missing information")
        if (
            self.answerability is ExplanationAnswerability.INSUFFICIENT
            and not self.missing_information
        ):
            raise ValueError("INSUFFICIENT requires missing information")
        return self


INTELLIGENCE_CONTRACTS = (
    InstrumentSpec,
    MarketContext,
    RegimeEvidence,
    AnalogueEvidence,
    EnsembleForecast,
    CalibratedOutcomeDistribution,
    MarketThesis,
    AnalystAssessment,
    StrategyDefinition,
    FormulaDefinition,
    StrategyExperiment,
    StrategyScorecard,
    PromotionDecision,
    PerformanceAttribution,
    ExplanationEvidence,
)

__all__ = [contract.__name__ for contract in INTELLIGENCE_CONTRACTS] + [
    "INTELLIGENCE_CONTRACTS",
    "UNIT_SUM_TOLERANCE",
]
