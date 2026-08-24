from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from ats.api.app import create_app
from ats.api.models import (
    AdvisoryReadModel,
    AutonomyTokenReadModel,
    CampaignReadModel,
    CandidateReadModel,
    GovernanceContextReadModel,
    PolicyReadModel,
    ReadinessState,
    RiskDecisionReadModel,
    SystemReadModel,
    TokenViewState,
)
from ats.api.providers import EmptyControlPlaneReader
from ats.contracts.domain.types import AutonomyLevel, LossState, RiskOutcome
from ats.contracts.governance.types import SystemState
from pydantic import ValidationError

from tests.unit.api.fixtures import make_api_fixture
from tests.unit.kernel.fixtures import T0, _validated


def test_explicit_read_models_map_frozen_contracts() -> None:
    x = make_api_fixture()
    assert PolicyReadModel.from_contract(x["policy"]).policy_id == x["policy"].policy_id
    assert CampaignReadModel.from_contract(x["campaign"]).scope == "A2_PAPER"
    assert (
        CandidateReadModel.from_contract(x["candidate"]).candidate_id == x["candidate"].candidate_id
    )
    assert GovernanceContextReadModel.from_contract(x["context"]).authority_scope == "A2_PAPER"
    assert RiskDecisionReadModel.from_contract(x["risk_decision"]).decision is RiskOutcome.ALLOW
    assert AdvisoryReadModel.from_contract(x["advisory"]).advisory_id == x["advisory"].advisory_id


def test_decimal_and_utc_serialization_are_preserved() -> None:
    x = make_api_fixture()
    campaign = CampaignReadModel.from_contract(x["campaign"])
    payload = campaign.model_dump(mode="json")
    assert payload["capital_budget"] == str(x["campaign"].capital_budget)
    assert payload["start_at"].endswith("Z")
    assert Decimal(payload["capital_budget"]) == x["campaign"].capital_budget


def test_unknown_state_is_represented_honestly() -> None:
    model = SystemReadModel(
        system_state=SystemState.UNKNOWN,
        system_state_version=1,
        readiness=ReadinessState.UNKNOWN,
        degradation_indicators=("STATE_UNKNOWN",),
        loss_state=LossState.CAUTION,
        active_policy_id=None,
        active_policy_version=None,
        active_campaign_id=None,
        active_campaign_version=None,
        authority_mode="A2_PAPER",
        reconciliation_active=False,
        halted=False,
        last_state_at=T0,
        last_event_at=None,
    )
    assert model.model_dump(mode="json")["system_state"] == "UNKNOWN"
    assert model.model_dump(mode="json")["readiness"] == "UNKNOWN"


def test_api_scope_cannot_represent_a3() -> None:
    x = make_api_fixture()
    raw = x["system_view"].model_dump()
    raw["authority_mode"] = "A3"
    with pytest.raises(ValidationError):
        SystemReadModel.model_validate(raw)


@pytest.mark.parametrize(
    ("changes", "state"),
    [
        ({}, TokenViewState.ISSUED),
        ({"consumed_at": None}, TokenViewState.CONSUMED),
    ],
)
def test_safe_token_status_view(changes: dict[str, object], state: TokenViewState) -> None:
    x = make_api_fixture()
    if state is TokenViewState.CONSUMED:
        changes["consumed_at"] = x["token_contract"].issued_at
    token = _validated(x["token_contract"], **changes)
    view = AutonomyTokenReadModel.from_contract(token, evaluation_time=token.issued_at)
    assert view.state is state
    assert "nonce" not in type(view).model_fields
    assert "payload_hash" not in type(view).model_fields


def test_expired_revoked_and_invalid_token_states() -> None:
    x = make_api_fixture()
    token = x["token_contract"]
    assert (
        AutonomyTokenReadModel.from_contract(token, evaluation_time=token.expires_at).state
        is TokenViewState.EXPIRED
    )
    assert (
        AutonomyTokenReadModel.from_contract(
            token, evaluation_time=token.issued_at, revoked=True
        ).state
        is TokenViewState.REVOKED
    )
    assert (
        AutonomyTokenReadModel.from_contract(
            token, evaluation_time=token.issued_at, valid=False
        ).state
        is TokenViewState.INVALID
    )


def test_read_models_are_strict_frozen_and_forbid_extra_fields() -> None:
    x = make_api_fixture()
    policy = PolicyReadModel.from_contract(x["policy"])
    with pytest.raises(ValidationError):
        policy.policy_version = 2
    raw = policy.model_dump()
    raw["secret"] = "not permitted"
    with pytest.raises(ValidationError):
        PolicyReadModel.model_validate(raw)


def test_empty_provider_is_truthfully_not_ready() -> None:
    reader = EmptyControlPlaneReader()
    assert reader.get_system() is None
    assert reader.stream_events() == ()
    assert create_app(reader).state.control_plane_reader is reader


def test_policy_autonomy_a0_remains_visible_without_becoming_a2() -> None:
    x = make_api_fixture()
    policy = _validated(x["policy"], autonomy_level=AutonomyLevel.A0)
    assert PolicyReadModel.from_contract(policy).autonomy_level is AutonomyLevel.A0


def test_token_expiry_comparison_uses_explicit_time() -> None:
    x = make_api_fixture()
    token = x["token_contract"]
    before = AutonomyTokenReadModel.from_contract(
        token, evaluation_time=token.expires_at - timedelta(microseconds=1)
    )
    at = AutonomyTokenReadModel.from_contract(token, evaluation_time=token.expires_at)
    assert before.state is TokenViewState.ISSUED
    assert at.state is TokenViewState.EXPIRED
