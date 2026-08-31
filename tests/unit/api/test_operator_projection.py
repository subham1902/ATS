from __future__ import annotations

import asyncio
from decimal import Decimal

from ats.api.models import StreamEvent
from ats.contracts.domain.types import RiskOutcome
from ats.intelligence.calibration.validation import CalibrationHealth, CalibrationValidationReport
from ats.intelligence.rare_opportunity.models import (
    OpportunityClass,
    RareOpportunityAssessment,
)
from ats.observability.operator_intelligence import AgentStatus, ProvenanceType, SourceState
from ats.observability.operator_projection import (
    AgentObservation,
    CandidateObservation,
    InstrumentObservation,
    OperatorProjectionInput,
    build_operator_snapshot,
)
from ats.observability.operator_provider import OperatorIntelligenceProvider
from ats.portfolio.brain.models import AllocationOutcome, PortfolioAllocationDecision
from ats.trading_runtime.modes import TradingMode

from tests.unit.api.fixtures import make_api_fixture
from tests.unit.kernel.fixtures import T0, uid


def _rare(index: int, opportunity_class: OpportunityClass, *reasons: str):
    return RareOpportunityAssessment(
        assessment_id=uid(800 + index),
        instrument_key=f"NSE_FO|{index}",
        opportunity_class=opportunity_class,
        eligible=not reasons,
        anomaly_score=float(index),
        analogue_count=25,
        credible_downside=Decimal("10"),
        median_upside=Decimal("20"),
        tail_upside=Decimal("50"),
        expected_net_value=Decimal("-1") if reasons else Decimal("5"),
        payoff_asymmetry_ratio=Decimal("3"),
        convexity_budget_fraction=Decimal("0.05"),
        reason_codes=reasons,
        input_hash="a" * 64,
        payload_hash="b" * 64,
    )


def _portfolio(candidate, index: int, outcome: AllocationOutcome):
    return PortfolioAllocationDecision(
        decision_id=uid(850 + index),
        candidate_id=candidate.candidate_id,
        candidate_hash=candidate.payload_hash,
        outcome=outcome,
        approved_capital=Decimal("1000") if outcome is AllocationOutcome.ALLOW else Decimal("0"),
        approved_quantity=Decimal("65") if outcome is AllocationOutcome.ALLOW else Decimal("0"),
        expected_net_value=Decimal("5"),
        effective_mode=TradingMode.NORMAL,
        correlation_penalty=Decimal("0.1"),
        concentration_penalty=Decimal("0.1"),
        drawdown_penalty=Decimal("0"),
        execution_penalty=Decimal("0"),
        liquidity_penalty=Decimal("0"),
        reason_codes=("CAPACITY_EXHAUSTED",) if outcome is AllocationOutcome.DENY else (),
        input_hash="c" * 64,
        valid_until=candidate.expires_at,
        payload_hash="d" * 64,
    )


def _source():
    fixture = make_api_fixture()
    base = fixture["candidate"]
    risk = fixture["risk_decision"]
    advisory = fixture["advisory"]
    classes = tuple(OpportunityClass)
    observations = []
    for index, opportunity_class in enumerate(classes):
        candidate = base.model_copy(
            update={
                "candidate_id": uid(700 + index),
                "instrument_id": f"NSE_FO|{index}",
                "payload_hash": f"{index + 1}" * 64,
            }
        )
        rare = _rare(
            index,
            opportunity_class,
            *(("LIQUIDITY_TOO_LOW", "SPREAD_TOO_WIDE") if index == 0 else ()),
        )
        portfolio = _portfolio(
            candidate,
            index,
            AllocationOutcome.DENY if index == 1 else AllocationOutcome.ALLOW,
        )
        candidate_risk = risk.model_copy(
            update={
                "risk_decision_id": uid(900 + index),
                "decision": RiskOutcome.DENY if index == 2 else RiskOutcome.ALLOW,
                "reason_codes": ("A04_SPREAD_LIMIT",) if index == 2 else (),
            }
        )
        calibration = CalibrationValidationReport(
            health=CalibrationHealth.INVALID if index == 3 else CalibrationHealth.HEALTHY,
            train_count=60,
            validation_count=20,
            oos_count=20,
            train_window=None,
            validation_window=None,
            oos_window=None,
            brier_score=0.2,
            log_loss=0.5,
            expected_calibration_error=0.1,
            reliability=(),
            reason_codes=("DRIFT_INVALID",) if index == 3 else (),
        )
        observations.append(
            CandidateObservation(
                candidate=candidate,
                underlying="NIFTY" if index % 2 == 0 else "BANKNIFTY",
                strategy="LONG_CE" if index % 2 == 0 else "LONG_PE",
                rare_assessment=rare,
                portfolio_decision=portfolio,
                risk_decision=candidate_risk,
                calibration=calibration,
            )
        )
    agents = tuple(
        AgentObservation(
            agent_id=f"agent-{index}",
            role=role,
            advisory=advisory.model_copy(update={"advisory_id": uid(950 + index)}),
            wake_reason="CANDIDATE_CREATED",
            data_cutoff=T0,
            status=AgentStatus.ACTIVE,
        )
        for index, role in enumerate(
            (
                "Session Market Agent",
                "Position Agent",
                "Portfolio Analyst Agent",
                "Research Agent",
            )
        )
    )
    return OperatorProjectionInput(
        as_of=T0,
        data_cutoff=T0,
        provenance=ProvenanceType.REPLAY,
        instruments=(
            InstrumentObservation(
                instrument_key="NSE_INDEX|Nifty 50",
                source_state=SourceState.LIVE,
                reference_valid=True,
                observed_at=T0,
            ),
            InstrumentObservation(
                instrument_key="NSE_INDEX|Nifty Bank",
                source_state=SourceState.STALE,
                reference_valid=True,
                observed_at=T0,
            ),
            InstrumentObservation(
                instrument_key="NSE_FO|invalid",
                source_state=SourceState.UNKNOWN,
                reference_valid=False,
                observed_at=T0,
            ),
        ),
        candidates=tuple(observations),
        agents=agents,
    )


def test_projection_uses_canonical_truth_for_all_operator_surfaces() -> None:
    snapshot = build_operator_snapshot(_source())
    assert snapshot.scanner.funnel.model_dump() == {
        "universe_observed": 3,
        "fresh": 1,
        "stale": 1,
        "invalid_reference": 1,
    }
    assert snapshot.scanner.candidates_by_class.model_dump() == {
        "standard": 1,
        "high_conviction": 1,
        "convex": 1,
        "rare_event": 1,
    }
    assert snapshot.scanner.rejections.liquidity == 1
    assert snapshot.scanner.rejections.spread == 2  # R10-X plus deterministic A04 reason
    assert snapshot.scanner.rejections.calibration == 1
    assert snapshot.scanner.rejections.negative_ev == 1
    assert snapshot.scanner.rejections.portfolio_capacity == 1
    assert snapshot.scanner.rejections.a04 == 1
    assert len(snapshot.edge_ledger.entries) == 4
    assert snapshot.edge_ledger.entries[3].calibration_health == "INVALID"
    assert snapshot.edge_ledger.entries[0].spread_cost is None
    assert {point.candidate_class.value for point in snapshot.opportunity_map} == {
        "STANDARD",
        "HIGH_CONVICTION",
        "CONVEX",
        "RARE_EVENT",
    }
    assert all(agent.authority == "ADVISORY_ONLY" for agent in snapshot.agents)
    assert {agent.role for agent in snapshot.agents} == {
        "Session Market Agent",
        "Position Agent",
        "Portfolio Analyst Agent",
        "Research Agent",
    }
    assert all(snapshot.evidence_lineage.values())


def test_missing_economics_remain_unknown_instead_of_synthesized() -> None:
    fixture = make_api_fixture()
    source = OperatorProjectionInput(
        as_of=T0,
        data_cutoff=T0,
        candidates=(CandidateObservation(candidate=fixture["candidate"]),),
    )
    entry = build_operator_snapshot(source).edge_ledger.entries[0]
    assert entry.market_implied_probability is None
    assert entry.spread_cost is None
    assert entry.expected_net_value is None
    assert entry.portfolio_brain_outcome.value == "UNKNOWN"
    assert entry.a04_outcome.value == "UNKNOWN"


def test_api_exposes_truthful_unknown_projection_without_attached_runtime() -> None:
    response = make_api_fixture()["client"].get("/v1/operator-intelligence")
    assert response.status_code == 200
    body = response.json()
    assert body["provenance"] == "LIVE"
    assert body["scanner"]["source_state"] == "UNKNOWN"
    assert body["survival"]["effective_survival_state"] == "UNKNOWN"
    assert body["edge_ledger"]["entries"] == []


def test_operator_event_delivery_drops_ui_backpressure() -> None:
    async def exercise() -> None:
        source = _source()
        provider = OperatorIntelligenceProvider(source)
        stream = provider.stream()
        pending = asyncio.create_task(anext(stream))
        await asyncio.sleep(0)
        for index in range(3):
            accepted = provider.observe(
                source,
                StreamEvent(
                    stream_event_id=uid(980 + index),
                    event_kind=("CANDIDATE_CREATED", "RISK_EVALUATED", "POSITION_UPDATED")[index],
                    occurred_at=T0,
                    correlation_id=uid(990),
                    payload={"candidate_id": str(source.candidates[0].candidate.candidate_id)},
                ),
            )
            assert accepted is True
        event = await asyncio.wait_for(pending, timeout=1)
        assert event.event_kind in {"CANDIDATE_CREATED", "RISK_EVALUATED", "POSITION_UPDATED"}
        await stream.aclose()

    asyncio.run(exercise())


def test_non_material_events_do_not_mutate_or_reach_operator_stream() -> None:
    source = _source()
    provider = OperatorIntelligenceProvider(source)
    accepted = provider.observe(
        source.model_copy(update={"candidates": ()}),
        StreamEvent(
            stream_event_id=uid(999),
            event_kind="UNFROZEN_UI_EVENT",
            occurred_at=T0,
            correlation_id=uid(998),
            payload={},
        ),
    )
    assert accepted is False
    assert len(provider.snapshot().edge_ledger.entries) == 4
