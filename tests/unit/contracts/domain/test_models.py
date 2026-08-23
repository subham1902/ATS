"""Universal and intrinsic-invariant tests for all frozen A02 contracts."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ats.contracts.common import ATSBaseModel
from ats.contracts.domain import DOMAIN_CONTRACTS
from ats.contracts.domain.types import (
    AdvisoryOutcome,
    PaperOrderStatus,
    PaperOrderType,
    PositionStatus,
    RiskOutcome,
)

from .fixtures import HASH, LATER, NOW, make_contracts


@pytest.fixture(scope="module")
def contracts() -> dict[str, ATSBaseModel]:
    return make_contracts()  # type: ignore[return-value]


@pytest.mark.parametrize("contract_type", DOMAIN_CONTRACTS, ids=lambda value: value.__name__)
def test_valid_fixture_exists(contract_type: type[ATSBaseModel], contracts: dict[str, ATSBaseModel]) -> None:
    assert isinstance(contracts[contract_type.__name__], contract_type)


@pytest.mark.parametrize("contract_type", DOMAIN_CONTRACTS, ids=lambda value: value.__name__)
def test_schema_version_is_exact(contract_type: type[ATSBaseModel], contracts: dict[str, ATSBaseModel]) -> None:
    value = contracts[contract_type.__name__]
    assert value.schema_version == "1.0"  # type: ignore[attr-defined]
    with pytest.raises(ValidationError):
        contract_type.model_validate({**value.model_dump(), "schema_version": "2.0"})


@pytest.mark.parametrize("contract_type", DOMAIN_CONTRACTS, ids=lambda value: value.__name__)
def test_extra_fields_are_rejected(
    contract_type: type[ATSBaseModel], contracts: dict[str, ATSBaseModel]
) -> None:
    value = contracts[contract_type.__name__]
    with pytest.raises(ValidationError):
        contract_type.model_validate({**value.model_dump(), "unexpected": True})


@pytest.mark.parametrize("contract_type", DOMAIN_CONTRACTS, ids=lambda value: value.__name__)
def test_models_are_frozen(contract_type: type[ATSBaseModel], contracts: dict[str, ATSBaseModel]) -> None:
    value = contracts[contract_type.__name__]
    with pytest.raises(ValidationError):
        value.schema_version = "1.0"  # type: ignore[attr-defined,misc]


@pytest.mark.parametrize("contract_type", DOMAIN_CONTRACTS, ids=lambda value: value.__name__)
def test_json_round_trip_preserves_contract(
    contract_type: type[ATSBaseModel], contracts: dict[str, ATSBaseModel]
) -> None:
    value = contracts[contract_type.__name__]
    assert contract_type.model_validate_json(value.model_dump_json()) == value


@pytest.mark.parametrize("contract_type", DOMAIN_CONTRACTS, ids=lambda value: value.__name__)
def test_json_schema_exports(contract_type: type[ATSBaseModel]) -> None:
    schema = contract_type.model_json_schema()
    assert schema["title"] == contract_type.__name__
    assert schema["type"] == "object"


def invalid_payload(name: str, value: ATSBaseModel) -> dict[str, object]:
    payload: dict[str, object] = value.model_dump()
    mutations: dict[str, dict[str, object]] = {
        "MarketSnapshot": {"high": Decimal("90")},
        "FeatureBundle": {"features": {"bad": float("nan")}},
        "ForecastBundle": {"forecast_paths": ((1.0,),)},
        "ConfidenceEvidence": {"regime_familiarity": 1.1},
        "StrategyPolicyDraft": {"executable": True},
        "StrategyPolicy": {"autonomy_level": "A3"},
        "RiskFacts": {"drawdown_fraction": Decimal("1.1")},
        "RiskDecision": {"decision": RiskOutcome.UNKNOWN, "reason_codes": ()},
        "DecisionPacket": {"bounded_evidence": {"bad": {1, 2}}},
        "SupervisorAdvisory": {"recommendation": "EXECUTE"},
        "AutonomyToken": {"scope": "A3_LIVE"},
        "OrderIntent": {"order_type": PaperOrderType.LIMIT, "limit_price": None},
        "PaperOrder": {"filled_quantity": Decimal("11")},
        "Fill": {"fees": Decimal("-0.01")},
        "Position": {"status": PositionStatus.CLOSED, "closed_at": None},
        "ExitIntent": {"quantity": Decimal("0")},
        "TradeReview": {"outcome_metrics": {"return": float("inf")}},
        "AuditEvent": {"record_hash": "invalid"},
    }
    payload.update(mutations[name])
    return payload


@pytest.mark.parametrize("contract_type", DOMAIN_CONTRACTS, ids=lambda value: value.__name__)
def test_critical_contract_boundary(
    contract_type: type[ATSBaseModel], contracts: dict[str, ATSBaseModel]
) -> None:
    with pytest.raises(ValidationError):
        contract_type.model_validate(
            invalid_payload(contract_type.__name__, contracts[contract_type.__name__])
        )


def test_market_snapshot_intrinsic_time_and_quality_invariants(
    contracts: dict[str, ATSBaseModel],
) -> None:
    value = contracts["MarketSnapshot"]
    for mutation in (
        {"bar_timestamp": NOW + timedelta(minutes=1)},
        {"received_at": NOW - timedelta(microseconds=1)},
        {"quality_flags": ("STALE", "STALE")},
    ):
        with pytest.raises(ValidationError):
            type(value).model_validate({**value.model_dump(), **mutation})


def test_forecast_calibration_and_completion_invariants(contracts: dict[str, ATSBaseModel]) -> None:
    value = contracts["ForecastBundle"]
    for mutation in (
        {"calibrator_version": None},
        {"completed_at": NOW - timedelta(microseconds=1)},
    ):
        with pytest.raises(ValidationError):
            type(value).model_validate({**value.model_dump(), **mutation})


def test_strategy_policy_intrinsic_invariants(contracts: dict[str, ATSBaseModel]) -> None:
    value = contracts["StrategyPolicy"]
    for mutation in (
        {"universe": ()},
        {"valid_until": NOW},
        {"stop_rules": ()},
        {"target_rules": (), "time_exit": None},
        {"compatible_model_versions": ()},
        {"lifecycle_status": "ACTIVE", "activated_at": None},
    ):
        with pytest.raises(ValidationError):
            type(value).model_validate({**value.model_dump(), **mutation})


def test_risk_unknown_remains_representable_with_reason(
    contracts: dict[str, ATSBaseModel],
) -> None:
    value = contracts["RiskDecision"]
    unknown = type(value).model_validate(
        {**value.model_dump(), "decision": RiskOutcome.UNKNOWN, "reason_codes": ("NO_DATA",)}
    )
    assert unknown.decision is RiskOutcome.UNKNOWN  # type: ignore[attr-defined]


def test_supervisor_advisory_has_no_executable_authority(
    contracts: dict[str, ATSBaseModel],
) -> None:
    value = contracts["SupervisorAdvisory"]
    assert value.recommendation is AdvisoryOutcome.APPROVE  # type: ignore[attr-defined]
    assert "executable" not in type(value).model_fields


def test_order_and_exit_price_invariants(contracts: dict[str, ATSBaseModel]) -> None:
    for name in ("OrderIntent", "ExitIntent"):
        value = contracts[name]
        payload = {
            **value.model_dump(),
            "order_type": PaperOrderType.STOP_LIMIT,
            "limit_price": Decimal("100"),
            "stop_price": None,
        }
        with pytest.raises(ValidationError):
            type(value).model_validate(payload)


def test_paper_order_fill_and_rejection_invariants(contracts: dict[str, ATSBaseModel]) -> None:
    value = contracts["PaperOrder"]
    invalid = (
        {"filled_quantity": Decimal("1"), "average_fill_price": None},
        {"status": PaperOrderStatus.REJECTED, "rejection_reason": None},
        {"updated_at": NOW - timedelta(microseconds=1)},
    )
    for mutation in invalid:
        with pytest.raises(ValidationError):
            type(value).model_validate({**value.model_dump(), **mutation})


def test_autonomy_token_lifetime(contracts: dict[str, ATSBaseModel]) -> None:
    value = contracts["AutonomyToken"]
    with pytest.raises(ValidationError):
        type(value).model_validate({**value.model_dump(), "expires_at": NOW})


def test_position_timestamp_lifecycle(contracts: dict[str, ATSBaseModel]) -> None:
    value = contracts["Position"]
    with pytest.raises(ValidationError):
        type(value).model_validate({**value.model_dump(), "updated_at": NOW - timedelta(seconds=1)})


def test_required_idempotency_keys(contracts: dict[str, ATSBaseModel]) -> None:
    for name in ("OrderIntent", "PaperOrder", "Fill", "ExitIntent"):
        value = contracts[name]
        assert value.model_dump()["idempotency_key"]
        with pytest.raises(ValidationError):
            type(value).model_validate({**value.model_dump(), "idempotency_key": ""})


def test_trade_review_proposals_are_permanently_non_executable(
    contracts: dict[str, ATSBaseModel],
) -> None:
    review = contracts["TradeReview"]
    proposal = review.policy_change_proposals[0]  # type: ignore[attr-defined]
    assert proposal.executable is False
    with pytest.raises(ValidationError):
        type(proposal).model_validate({**proposal.model_dump(), "executable": True})


def test_payload_hash_fields_have_sha256_shape(contracts: dict[str, ATSBaseModel]) -> None:
    for value in contracts.values():
        field_name = "record_hash" if type(value).__name__ == "AuditEvent" else "payload_hash"
        if field_name in type(value).model_fields:
            assert value.model_dump()[field_name] == HASH
