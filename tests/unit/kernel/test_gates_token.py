from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from ats.contracts.domain.types import AdvisoryOutcome, DataQualityState, RiskOutcome
from ats.contracts.governance.types import CampaignStatus, CandidateStatus
from ats.contracts.intelligence.types import MarketThesisStatus, StrategyStatus
from ats.kernel.autonomy import (
    construct_autonomy_token,
    validate_token_eligibility,
    validate_token_for_use,
)
from ats.kernel.governance import (
    validate_campaign_gate,
    validate_intelligence_freshness,
    validate_probability_economics,
    validate_strategy_status,
)
from ats.kernel.risk import produce_risk_decision
from ats.kernel.types import AutonomyTokenPolicy, KernelOutcome

from tests.unit.kernel.fixtures import T0, _validated, make_kernel_fixture, uid


def _eligibility(x: dict[str, object]):  # type: ignore[no-untyped-def]
    return validate_token_eligibility(
        policy=x["policy"],
        campaign=x["campaign"],
        campaign_state=x["campaign_state"],
        market=x["market"],
        thesis=x["thesis"],
        distribution=x["distribution"],
        candidate=x["candidate"],
        strategy=x["strategy"],
        context=x["context"],
        risk_decision=x["risk_decision"],
        advisory=x["advisory"],
        packet=x["packet"],
        binding=x["binding"],
        constraints=x["constraints"],
        campaign_facts=x["campaign_facts"],
        capital_basis=x["basis"],
        execution_safety=x["safety"],
        evaluation_time=T0,
        maximum_freshness_ms=1000,
        current_system_state_version=1,
        model_family="model",
        model_version="1",
        calibrator_version="1",
    )


def test_base_campaign_and_intelligence_gates_allow() -> None:
    x = make_kernel_fixture()
    assert (
        validate_campaign_gate(
            x["campaign"],
            x["campaign_state"],
            x["constraints"],
            x["campaign_facts"],
            capital_basis=x["basis"],
            evaluation_time=T0,
        ).outcome
        is KernelOutcome.ALLOW
    )
    assert (
        validate_intelligence_freshness(
            x["context"],
            x["market"],
            x["thesis"],
            x["distribution"],
            x["candidate"],
            x["constraints"],
            evaluation_time=T0,
            maximum_freshness_ms=1000,
        ).outcome
        is KernelOutcome.ALLOW
    )
    assert (
        validate_probability_economics(x["candidate"], x["distribution"], x["constraints"]).outcome
        is KernelOutcome.ALLOW
    )


@pytest.mark.parametrize(
    "status",
    [
        CampaignStatus.DRAFT,
        CampaignStatus.PAUSED,
        CampaignStatus.COMPLETED,
        CampaignStatus.HALTED,
        CampaignStatus.EXPIRED,
    ],
)
def test_nonactive_campaign_denies_increase(status: CampaignStatus) -> None:
    x = make_kernel_fixture()
    activated = None if status is CampaignStatus.DRAFT else T0
    campaign = _validated(x["campaign"], status=status, activated_at=activated)
    result = validate_campaign_gate(
        campaign,
        x["campaign_state"],
        x["constraints"],
        x["campaign_facts"],
        capital_basis=x["basis"],
        evaluation_time=T0,
    )
    assert result.outcome is KernelOutcome.DENY


def test_campaign_ceiling_concurrency_cooldown_and_drawdown() -> None:
    x = make_kernel_fixture()
    constraints = x["constraints"]
    mutations = (
        {"trades_started": constraints.max_trades},
        {
            "trades_started": constraints.max_concurrent_positions,
            "open_positions": constraints.max_concurrent_positions,
        },
        {"cooldown_until": T0 + timedelta(seconds=1)},
        {"maximum_drawdown_observed": constraints.drawdown_limit},
        {"capital_committed": constraints.capital_budget},
        {"realized_pnl": Decimal("-100")},
    )
    for changes in mutations:
        state = _validated(x["campaign_state"], **changes)
        result = validate_campaign_gate(
            x["campaign"],
            state,
            constraints,
            x["campaign_facts"],
            capital_basis=x["basis"],
            evaluation_time=T0,
        )
        assert result.outcome is KernelOutcome.DENY
    assert "required_trades" not in type(x["campaign"]).model_fields


def test_campaign_identity_and_state_mismatch_deny() -> None:
    x = make_kernel_fixture()
    state = x["campaign_state"].model_copy(update={"campaign_version": 2})
    assert (
        validate_campaign_gate(
            x["campaign"],
            state,
            x["constraints"],
            x["campaign_facts"],
            capital_basis=x["basis"],
            evaluation_time=T0,
        ).outcome
        is KernelOutcome.DENY
    )
    paused = _validated(x["campaign_state"], status=CampaignStatus.PAUSED)
    assert (
        validate_campaign_gate(
            x["campaign"],
            paused,
            x["constraints"],
            x["campaign_facts"],
            capital_basis=x["basis"],
            evaluation_time=T0,
        ).outcome
        is KernelOutcome.DENY
    )


def test_stale_bad_or_expired_intelligence_denied() -> None:
    x = make_kernel_fixture()
    market = _validated(x["market"], freshness_ms=1001)
    assert (
        validate_intelligence_freshness(
            x["context"],
            market,
            x["thesis"],
            x["distribution"],
            x["candidate"],
            x["constraints"],
            evaluation_time=T0,
            maximum_freshness_ms=1000,
        ).outcome
        is KernelOutcome.DENY
    )
    bad_market = _validated(x["market"], data_quality_state=DataQualityState.UNKNOWN)
    assert (
        validate_intelligence_freshness(
            x["context"],
            bad_market,
            x["thesis"],
            x["distribution"],
            x["candidate"],
            x["constraints"],
            evaluation_time=T0,
            maximum_freshness_ms=1000,
        ).outcome
        is KernelOutcome.DENY
    )
    thesis = _validated(x["thesis"], status=MarketThesisStatus.EXPIRED)
    assert (
        validate_intelligence_freshness(
            x["context"],
            x["market"],
            thesis,
            x["distribution"],
            x["candidate"],
            x["constraints"],
            evaluation_time=T0,
            maximum_freshness_ms=1000,
        ).outcome
        is KernelOutcome.DENY
    )
    assert (
        validate_intelligence_freshness(
            x["context"],
            x["market"],
            x["thesis"],
            x["distribution"],
            x["candidate"],
            x["constraints"],
            evaluation_time=x["distribution"].valid_until,  # type: ignore[attr-defined]
            maximum_freshness_ms=1000,
        ).outcome
        is KernelOutcome.DENY
    )
    candidate = _validated(x["candidate"], status=CandidateStatus.EXPIRED)
    assert (
        validate_intelligence_freshness(
            x["context"],
            x["market"],
            x["thesis"],
            x["distribution"],
            candidate,
            x["constraints"],
            evaluation_time=T0,
            maximum_freshness_ms=1000,
        ).outcome
        is KernelOutcome.DENY
    )


def test_probability_economics_fail_independently() -> None:
    x = make_kernel_fixture()
    changes = (
        {"expected_net_edge_r": -0.1},
        {"calibrated_probability": Decimal("0.5")},
        {"expected_reward_risk": Decimal("1")},
    )
    for change in changes:
        candidate = _validated(x["candidate"], **change)
        assert (
            validate_probability_economics(candidate, x["distribution"], x["constraints"]).outcome
            is KernelOutcome.DENY
        )
    distribution = _validated(x["distribution"], support_count=1)
    assert (
        validate_probability_economics(x["candidate"], distribution, x["constraints"]).outcome
        is KernelOutcome.DENY
    )
    mismatch = _validated(x["candidate"], calibrated_probability=Decimal("0.9"))
    assert (
        validate_probability_economics(mismatch, x["distribution"], x["constraints"]).outcome
        is KernelOutcome.DENY
    )


@pytest.mark.parametrize(
    "status",
    [
        StrategyStatus.DRAFT,
        StrategyStatus.VALIDATED,
        StrategyStatus.REJECTED,
        StrategyStatus.RETIRED,
        StrategyStatus.CHALLENGER,
    ],
)
def test_nonchampion_strategy_denied_by_default(status: StrategyStatus) -> None:
    x = make_kernel_fixture()
    assert (
        validate_strategy_status(_validated(x["strategy"], status=status), x["campaign"]).outcome
        is KernelOutcome.DENY
    )


def test_full_stage1_token_lifecycle() -> None:
    x = make_kernel_fixture()
    eligibility = _eligibility(x)
    assert eligibility.outcome is KernelOutcome.ALLOW
    token = construct_autonomy_token(
        eligibility=eligibility,
        token_id=uid(84),
        candidate=x["candidate"],
        policy=x["policy"],
        risk_decision=x["risk_decision"],
        advisory=x["advisory"],
        context=x["context"],
        issued_at=T0,
        expires_at=T0 + timedelta(seconds=30),
        nonce="nonce",
        token_policy=AutonomyTokenPolicy(max_ttl_ms=30000),
    )
    assert (
        validate_token_for_use(
            token,
            evaluation_time=T0,
            candidate_id=x["candidate"].candidate_id,
            policy_id=x["policy"].policy_id,
            policy_version=x["policy"].policy_version,
            risk_decision_id=x["risk_decision"].risk_decision_id,
            advisory_id=x["advisory"].advisory_id,
            current_system_state_version=1,
        ).outcome
        is KernelOutcome.ALLOW
    )
    assert (
        validate_token_for_use(
            token,
            evaluation_time=token.expires_at,
            candidate_id=token.candidate_id,
            policy_id=token.policy_id,
            policy_version=token.policy_version,
            risk_decision_id=token.risk_decision_id,
            advisory_id=token.advisory_id,
            current_system_state_version=1,
        ).outcome
        is KernelOutcome.DENY
    )
    with pytest.raises(ValueError):
        construct_autonomy_token(
            eligibility=eligibility,
            token_id=uid(84),
            candidate=x["candidate"],
            policy=x["policy"],
            risk_decision=x["risk_decision"],
            advisory=x["advisory"],
            context=x["context"],
            issued_at=T0,
            expires_at=T0 + timedelta(seconds=31),
            nonce="nonce",
            token_policy=AutonomyTokenPolicy(max_ttl_ms=30000),
        )


@pytest.mark.parametrize(
    ("risk", "advisory"),
    [
        (RiskOutcome.DENY, None),
        (RiskOutcome.UNKNOWN, None),
        (None, AdvisoryOutcome.REJECT),
        (None, AdvisoryOutcome.UNKNOWN),
    ],
)
def test_risk_or_supervisor_cannot_override_gates(
    risk: RiskOutcome | None, advisory: AdvisoryOutcome | None
) -> None:
    x = make_kernel_fixture()
    if risk is not None:
        x["risk_decision"] = _validated(x["risk_decision"], decision=risk, reason_codes=("DENIED",))
    if advisory is not None:
        x["advisory"] = _validated(x["advisory"], recommendation=advisory)
    assert _eligibility(x).outcome is KernelOutcome.DENY


def test_deterministic_risk_decision_allow_and_deny() -> None:
    x = make_kernel_fixture()
    first = produce_risk_decision(
        x["risk_facts"],
        x["policy"],
        x["constraints"],
        risk_decision_id=uid(85),
        risk_direction=x["context"].risk_direction,
        capital_basis=x["basis"],
        decided_at=T0,
    )
    second = produce_risk_decision(
        x["risk_facts"],
        x["policy"],
        x["constraints"],
        risk_decision_id=uid(85),
        risk_direction=x["context"].risk_direction,
        capital_basis=x["basis"],
        decided_at=T0,
    )
    assert first == second and first.decision is RiskOutcome.ALLOW
    facts = _validated(x["risk_facts"], proposed_maximum_loss=Decimal("101"))
    denied = produce_risk_decision(
        facts,
        x["policy"],
        x["constraints"],
        risk_direction=x["context"].risk_direction,
        risk_decision_id=uid(86),
        capital_basis=x["basis"],
        decided_at=T0,
    )
    assert denied.decision is RiskOutcome.DENY
    unknown_facts = _validated(x["risk_facts"], data_quality_state=DataQualityState.UNKNOWN)
    unknown = produce_risk_decision(
        unknown_facts,
        x["policy"],
        x["constraints"],
        risk_decision_id=uid(87),
        risk_direction=x["context"].risk_direction,
        capital_basis=x["basis"],
        decided_at=T0,
    )
    assert unknown.decision is RiskOutcome.UNKNOWN
    mismatched_facts = _validated(x["risk_facts"], policy_version=2)
    mismatch = produce_risk_decision(
        mismatched_facts,
        x["policy"],
        x["constraints"],
        risk_decision_id=uid(88),
        risk_direction=x["context"].risk_direction,
        capital_basis=x["basis"],
        decided_at=T0,
    )
    assert mismatch.decision is RiskOutcome.DENY
