from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from uuid import UUID

from ats.contracts.domain.hashing import compute_payload_hash
from ats.contracts.domain.models import ExitIntent, OrderIntent, Position
from ats.contracts.domain.types import (
    DataQualityState,
    ExitReason,
    PaperOrderType,
    PositionStatus,
    Side,
)
from ats.execution.paper import (
    PaperExecutionPolicy,
    PaperMarketFacts,
    PaperSubmissionScenario,
)

from tests.unit.market.derivatives.option_chain.helpers import AS_OF, master


def instrument():
    return next(item for item in master().instruments if item.instrument_id == "C1")


def intent(
    *,
    quantity: str = "65",
    order_type: PaperOrderType = PaperOrderType.MARKET,
    limit_price: Decimal | None = None,
    stop_price: Decimal | None = None,
    side: Side = Side.BUY,
) -> OrderIntent:
    value = OrderIntent(
        schema_version="1.0",
        intent_id=UUID("70000000-0000-0000-0000-000000000001"),
        instrument_id="C1",
        side=side,
        quantity=Decimal(quantity),
        order_type=order_type,
        entry_conditions=(),
        limit_price=limit_price,
        stop_price=stop_price,
        target_price=Decimal("130"),
        maximum_permitted_loss=Decimal("7000"),
        expected_reward=Decimal("2000"),
        policy_id=UUID("70000000-0000-0000-0000-000000000002"),
        policy_version=1,
        forecast_id=UUID("70000000-0000-0000-0000-000000000003"),
        risk_decision_id=UUID("70000000-0000-0000-0000-000000000004"),
        supervisor_advisory_id=UUID("70000000-0000-0000-0000-000000000005"),
        autonomy_token_id=UUID("70000000-0000-0000-0000-000000000006"),
        idempotency_key="ORDER-C1-1",
        created_at=AS_OF,
        payload_hash="0" * 64,
    )
    return value.model_copy(update={"payload_hash": compute_payload_hash(value)})


def market(**updates: object) -> PaperMarketFacts:
    values: dict[str, object] = {
        "instrument_id": "C1",
        "bid": Decimal("99"),
        "ask": Decimal("101"),
        "bid_quantity": 130,
        "ask_quantity": 130,
        "quote_time": AS_OF,
        "quality_state": DataQualityState.GOOD,
        "scenario": PaperSubmissionScenario.ACKNOWLEDGE,
        "rejection_reason": None,
    }
    values.update(updates)
    return PaperMarketFacts(**values)


def policy() -> PaperExecutionPolicy:
    return PaperExecutionPolicy(
        broker_model_version="DERIVATIVE-PAPER-V1",
        cost_model_version="NSE-PAPER-COST-V1",
        maximum_quote_age_ms=60_000,
        slippage_ticks=2,
        fee_fraction=Decimal("0.001"),
        tax_fraction=Decimal("0.002"),
    )


def evaluation_time():
    return AS_OF + timedelta(seconds=1)


def position(*, quantity: str = "130", version: int = 1) -> Position:
    value = Position(
        schema_version="1.0",
        position_id=UUID("71000000-0000-0000-0000-000000000001"),
        portfolio_id=UUID("71000000-0000-0000-0000-000000000002"),
        instrument_id="C1",
        net_quantity=Decimal(quantity),
        average_entry_price=Decimal("101.10"),
        mark_price=Decimal("110"),
        realized_pnl=Decimal("0"),
        unrealized_pnl=Decimal("578.50"),
        cash_effect=Decimal("-6571.50"),
        policy_id=UUID("70000000-0000-0000-0000-000000000002"),
        policy_version=1,
        opened_at=AS_OF,
        updated_at=AS_OF,
        closed_at=None,
        status=PositionStatus.OPEN,
        version=version,
        last_fill_id=UUID("71000000-0000-0000-0000-000000000003"),
        payload_hash="0" * 64,
    )
    return value.model_copy(update={"payload_hash": compute_payload_hash(value)})


def exit_intent(*, quantity: str = "65", position_version: int = 1) -> ExitIntent:
    value = ExitIntent(
        schema_version="1.0",
        exit_intent_id=UUID("72000000-0000-0000-0000-000000000001"),
        position_id=position().position_id,
        position_version=position_version,
        reason=ExitReason.RISK,
        quantity=Decimal(quantity),
        order_type=PaperOrderType.MARKET,
        limit_price=None,
        stop_price=None,
        risk_decision_id=UUID("72000000-0000-0000-0000-000000000002"),
        autonomy_token_id=UUID("72000000-0000-0000-0000-000000000003"),
        idempotency_key="EXIT-C1-1",
        created_at=AS_OF,
        payload_hash="0" * 64,
    )
    return value.model_copy(update={"payload_hash": compute_payload_hash(value)})
