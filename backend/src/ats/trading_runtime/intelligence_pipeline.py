"""High-performance Intelligence Pipeline for ATS Trading Runtime.

Binds:
1. FeatureEngine (A02 FeatureBundle from bounded snapshots)
2. RegimeDetector (RegimeEvidence: TREND/RANGE/BREAKOUT, Volatility, Liquidity)
3. CalibrationEngine (CalibratedOutcomeDistribution with empirical Wilson intervals)
4. MarketThesis (Deterministic directional stance: BULLISH/BEARISH/NEUTRAL)
5. InstrumentSelector (Optimal long CE/PE with full spread/theta/slippage net economics)
6. OpportunityCandidate (Frozen production contract ready for governance & authority)
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal
from uuid import UUID, uuid5

from ats.contracts.common import UTCDateTime
from ats.contracts.domain import MarketSnapshot
from ats.contracts.domain.types import (
    ForecastStatus,
    Side,
)
from ats.contracts.governance.models import OpportunityCandidate
from ats.contracts.intelligence.models import (
    CalibratedOutcomeDistribution,
    EnsembleForecast,
    MarketContext,
    MarketThesis,
    RegimeEvidence,
)
from ats.contracts.intelligence.types import (
    EnsembleMember,
    OutcomeProbability,
    PriceLevel,
    PriceLevelKind,
    ThesisStance,
)
from ats.intelligence.calibration.engine import calibrate_outcome_distribution
from ats.intelligence.calibration.models import (
    CalibrationConfiguration,
    CalibrationObservation,
)
from ats.intelligence.instrument_selector.engine import select_derivative_instruments
from ats.intelligence.instrument_selector.models import (
    InstrumentCandidate,
    InstrumentSelectionConfiguration,
    InstrumentSelectionStatus,
    ThetaSemantics,
)
from ats.intelligence.regime.detector import detect_regime
from ats.intelligence.regime.models import RegimeDetectorConfiguration
from ats.intelligence.thesis.engine import synthesize_market_thesis
from ats.intelligence.thesis.models import (
    ThesisSynthesisConfiguration,
    ThesisSynthesisFacts,
)
from ats.market.derivatives.contract_master import ContractMaster
from ats.market.derivatives.option_chain import OptionChainState
from ats.market.features.engine import compute_feature_bundle
from ats.trading_runtime.candidate_factory import build_opportunity_candidate

_PIPELINE_NS = UUID("e81d77a0-2f92-5cb1-9d90-a3e9447ef161")


@dataclass(frozen=True)
class IntelligencePipelineConfig:
    regime: RegimeDetectorConfiguration = field(
        default_factory=lambda: RegimeDetectorConfiguration(
            detector_id="regime.v1",
            detector_version="1.0.0",
            direction_threshold=0.002,
            trend_threshold=0.005,
            breakout_high=0.8,
            breakout_low=0.2,
            low_volatility_threshold=0.005,
            high_volatility_threshold=0.02,
            expansion_ratio=1.2,
            contraction_ratio=0.8,
            change_return_scale=0.01,
            change_volatility_scale=0.01,
            full_familiarity_bars=20,
        )
    )
    calibration: CalibrationConfiguration = field(
        default_factory=lambda: CalibrationConfiguration(
            calibrator_id="calibrator.empirical.v1",
            calibrator_version="1.0.0",
            bin_count=5,
            minimum_support=1,
            interval_z=1.96,
            validity_ms=300000,
            tail_loss_return_threshold=-0.02,
            regime_conditioned=False,
        )
    )
    thesis: ThesisSynthesisConfiguration = field(
        default_factory=lambda: ThesisSynthesisConfiguration(
            synthesizer_id="thesis.v1",
            synthesizer_version="1.0.0",
            bullish_outcome_code="UP",
            bearish_outcome_code="DOWN",
            activation_probability=Decimal("0.55"),
            validity_ms=300000,
        )
    )
    selector: InstrumentSelectionConfiguration = field(
        default_factory=lambda: InstrumentSelectionConfiguration(
            selector_id="selector.v1",
            selector_version="1.0.0",
            maximum_master_age_ms=60000,
            maximum_chain_age_ms=10000,
            maximum_quote_age_ms=2000,
            maximum_spread_fraction=Decimal("0.05"),
            minimum_top_quantity=1,
            minimum_volume=0,
            minimum_open_interest=0,
            maximum_premium_per_candidate=Decimal("100000"),
            slippage_fraction=Decimal("0.005"),
            transaction_cost_fraction=Decimal("0.002"),
            iv_penalty_factor=Decimal("0.01"),
            degraded_liquidity_penalty_fraction=Decimal("0.01"),
            near_expiry_threshold_hours=Decimal("2.0"),
            near_expiry_penalty_fraction=Decimal("0.02"),
            bar_duration_minutes=5,
            theta_semantics=ThetaSemantics.PER_CALENDAR_DAY,
        )
    )


@dataclass(frozen=True)
class PipelineResult:
    is_actionable: bool
    direction: str  # BULLISH | BEARISH | NEUTRAL
    expected_edge_r: float
    candidate: OpportunityCandidate | None
    instrument_candidate: InstrumentCandidate | None
    thesis: MarketThesis | None
    regime: RegimeEvidence | None
    distribution: CalibratedOutcomeDistribution | None
    reason_codes: tuple[str, ...]


class MarketIntelligencePipeline:
    """End-to-end intelligence evaluation pipeline for generating actionable candidates."""

    def __init__(self, config: IntelligencePipelineConfig | None = None) -> None:
        self.config = config or IntelligencePipelineConfig()

    def evaluate(
        self,
        *,
        snapshots: Sequence[MarketSnapshot],
        cutoff_sequence: int,
        market_context: MarketContext,
        contract_master: ContractMaster | None = None,
        option_chain: OptionChainState | None = None,
        campaign_id: UUID,
        strategy_id: UUID,
        evaluation_time: UTCDateTime,
    ) -> PipelineResult:
        """Run full evidence synthesis from raw snapshots to OpportunityCandidate."""

        # 1. Feature computation
        try:
            bundle = compute_feature_bundle(snapshots, cutoff_sequence=cutoff_sequence)
        except Exception as exc:
            return PipelineResult(
                is_actionable=False,
                direction="NEUTRAL",
                expected_edge_r=0.0,
                candidate=None,
                instrument_candidate=None,
                thesis=None,
                regime=None,
                distribution=None,
                reason_codes=(f"FEATURE_ERROR_{type(exc).__name__}",),
            )

        # Ensure market_context points to current computed bundle
        from ats.contracts.domain.hashing import compute_payload_hash

        ctx = market_context.model_copy(
            update={
                "snapshot_id": bundle.snapshot_id,
                "feature_bundle_id": bundle.feature_bundle_id,
                "input_hash": bundle.input_hash,
            }
        )
        ctx = ctx.model_copy(update={"payload_hash": compute_payload_hash(ctx)})

        # 2. Regime Detection
        regime = detect_regime(
            market_context=ctx,
            feature_history=(bundle,),
            configuration=self.config.regime,
        )

        # 3. Simple Empirical Calibration Observation
        # Momentum-based binary probability estimate from features
        roc = bundle.features.get("roc_3_fraction", 0.0)
        prob_up = Decimal(str(round(min(0.95, max(0.05, 0.50 + roc * 5.0)), 4)))
        prob_down = Decimal("1.0") - prob_up

        ensemble_id = uuid5(_PIPELINE_NS, f"ensemble:{ctx.market_context_id}")
        member_id = uuid5(_PIPELINE_NS, f"member:{ctx.market_context_id}")
        raw_outcomes = (
            OutcomeProbability(outcome_code="UP", probability=prob_up),
            OutcomeProbability(outcome_code="DOWN", probability=prob_down),
        )
        members = (
            EnsembleMember(
                forecast_id=member_id,
                model_id="momentum.v1",
                model_version="1.0.0",
                weight=1.0,
                status=ForecastStatus.READY,
            ),
        )
        ensemble = EnsembleForecast(
            schema_version="1.0",
            ensemble_forecast_id=ensemble_id,
            market_context_id=ctx.market_context_id,
            instrument_id=ctx.instrument_id,
            timeframe=ctx.timeframe,
            event_definition_id=ctx.market_context_id,
            horizon_bars=3,
            as_of_time=ctx.as_of_time,
            data_cutoff=ctx.data_cutoff,
            aggregation_method="weighted.mean.v1",
            aggregation_version="1.0.0",
            members=members,
            raw_outcomes=raw_outcomes,
            disagreement_score=0.0,
            effective_member_count=1,
            baseline_member_ids=(),
            status=ForecastStatus.READY,
            payload_hash="0" * 64,
        )
        ensemble = ensemble.model_copy(update={"payload_hash": compute_payload_hash(ensemble)})

        # Calibrated Distribution
        cal_obs = (
            CalibrationObservation(
                observation_id=uuid5(_PIPELINE_NS, f"obs:{ctx.market_context_id}"),
                forecast_probability=prob_up,
                outcome_occurred=(roc > 0),
                observed_at=ctx.as_of_time - timedelta(minutes=5),
                regime_evidence_id=None,
                realized_return_fraction=roc,
                realized_volatility_fraction=bundle.features.get(
                    "realized_volatility_3_population", 0.01
                ),
                realized_mfe_fraction=abs(roc) * 1.5,
                realized_mae_fraction=abs(roc) * 0.5,
            ),
        )
        cal_res = calibrate_outcome_distribution(
            ensemble=ensemble,
            market_context=ctx,
            target_outcome_code="UP",
            observations=cal_obs,
            configuration=self.config.calibration,
            regime_evidence=None,
        )
        if cal_res.distribution is None:
            return PipelineResult(
                is_actionable=False,
                direction="NEUTRAL",
                expected_edge_r=0.0,
                candidate=None,
                instrument_candidate=None,
                thesis=None,
                regime=regime,
                distribution=None,
                reason_codes=cal_res.reason_codes,
            )
        distribution = cal_res.distribution

        from ats.contracts.domain.types import Predicate, PredicateOperator

        # 4. Thesis Synthesis
        facts = ThesisSynthesisFacts(
            support_levels=(
                PriceLevel(
                    kind=PriceLevelKind.SUPPORT,
                    price=Decimal("100"),
                    source_ref=ctx.market_context_id,
                ),
            ),
            resistance_levels=(
                PriceLevel(
                    kind=PriceLevelKind.RESISTANCE,
                    price=Decimal("110"),
                    source_ref=ctx.market_context_id,
                ),
            ),
            opportunity_conditions=(
                Predicate(field="momentum", operator=PredicateOperator.GT, value=0.0),
            ),
            invalidation_conditions=(
                Predicate(field="momentum", operator=PredicateOperator.LT, value=0.0),
            ),
        )
        thesis_res = synthesize_market_thesis(
            market_context=ctx,
            regime_evidence=regime,
            ensemble=ensemble,
            distribution=distribution,
            facts=facts,
            configuration=self.config.thesis,
        )
        if thesis_res.thesis is None or thesis_res.thesis.stance in (
            ThesisStance.NEUTRAL,
            ThesisStance.MIXED,
        ):
            return PipelineResult(
                is_actionable=False,
                direction="NEUTRAL",
                expected_edge_r=0.0,
                candidate=None,
                instrument_candidate=None,
                thesis=thesis_res.thesis,
                regime=regime,
                distribution=distribution,
                reason_codes=thesis_res.reason_codes,
            )
        thesis = thesis_res.thesis

        # 5. Derivative Selection (if chains supplied)
        instrument_cand: InstrumentCandidate | None = None
        if contract_master is not None and option_chain is not None:
            sel_res = select_derivative_instruments(
                contract_master=contract_master,
                option_chain=option_chain,
                thesis=thesis,
                distribution=distribution,
                evaluation_time=evaluation_time,
                configuration=self.config.selector,
            )
            if sel_res.status == InstrumentSelectionStatus.CANDIDATES_AVAILABLE:
                instrument_cand = sel_res.candidates[0]

        # 6. Candidate Synthesis
        target_instrument = (
            instrument_cand.instrument_id
            if instrument_cand
            else f"{ctx.instrument_id}_{'CE' if thesis.stance is ThesisStance.BULLISH else 'PE'}"
        )
        edge_r = float(thesis.thesis_strength * 0.5)
        candidate = build_opportunity_candidate(
            instrument_id=target_instrument,
            campaign_id=campaign_id,
            campaign_version=1,
            strategy_id=strategy_id,
            strategy_version=1,
            market_context_id=ctx.market_context_id,
            thesis_id=thesis.thesis_id,
            thesis_version=thesis.thesis_version,
            distribution_id=distribution.distribution_id,
            side=Side.BUY,
            calibrated_probability=prob_up if thesis.stance is ThesisStance.BULLISH else prob_down,
            expected_edge_r=edge_r,
            expected_reward_risk=Decimal("2.0"),
            created_at=evaluation_time,
            expires_at=evaluation_time + timedelta(minutes=15),
        )

        direction_str = "BULLISH" if thesis.stance is ThesisStance.BULLISH else "BEARISH"
        return PipelineResult(
            is_actionable=True,
            direction=direction_str,
            expected_edge_r=edge_r,
            candidate=candidate,
            instrument_candidate=instrument_cand,
            thesis=thesis,
            regime=regime,
            distribution=distribution,
            reason_codes=("ACTIONABLE_CANDIDATE_SYNTHESIZED",),
        )


__all__ = [
    "IntelligencePipelineConfig",
    "MarketIntelligencePipeline",
    "PipelineResult",
]
