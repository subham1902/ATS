"""Governed A2 PAPER operator intents; HTTP and UI never own broker authority."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from typing import Literal
from uuid import UUID, uuid4

from ats.contracts.common import ATSBaseModel, UTCDateTime
from ats.market.derivatives.reference_authority import (
    InstrumentReferenceAuthority,
    InstrumentReferenceError,
)

from .broker import MarketDataFeed, OrderRequest, PaperBrokerAdapter
from .engine import TradingRuntime
from .position_monitor import ManagedExitMode, PositionOrigin


class OperatorOrderState(StrEnum):
    CREATED = "CREATED"
    RISK_ACCEPTED = "RISK_ACCEPTED"
    A04_AUTHORIZED = "A04_AUTHORIZED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    FILLED = "FILLED"
    REJECTED = "REJECTED"
    UNKNOWN = "UNKNOWN"


class OperatorOrderIntent(ATSBaseModel):
    operator_action_id: UUID
    instrument_key: str
    underlying: Literal["NIFTY", "BANKNIFTY"]
    expiry: str
    strike: Decimal
    option_type: Literal["CE", "PE"]
    side: Literal["BUY"] = "BUY"
    lots: int
    quantity: Decimal
    order_type: Literal["MARKET", "LIMIT"] = "LIMIT"
    requested_price: Decimal | None = None
    origin: Literal["OPERATOR_MANUAL"] = "OPERATOR_MANUAL"
    requested_at: UTCDateTime
    managed_exit_mode: ManagedExitMode
    reason: str | None = None


class OperatorOrderResult(ATSBaseModel):
    accepted: bool
    state: OperatorOrderState
    reason_codes: tuple[str, ...]
    order_intent_id: UUID
    risk_decision_id: UUID | None = None
    a04_decision_id: UUID | None = None
    token_id: UUID | None = None
    paper_order_id: str | None = None
    fill_id: UUID | None = None
    position_id: UUID | None = None


@dataclass(frozen=True)
class A04OperatorDecision:
    allowed: bool
    decision_id: UUID
    token_id: UUID | None
    reason_codes: tuple[str, ...]


@dataclass
class OperatorOrderService:
    references: InstrumentReferenceAuthority
    market_feed: MarketDataFeed
    broker: PaperBrokerAdapter
    runtime: TradingRuntime
    runtime_state: Callable[[], object]
    a04: Callable[[OperatorOrderIntent, Decimal], A04OperatorDecision]
    max_quote_age_ms: int = 5_000
    evidence: list[dict[str, object]] = field(default_factory=list)

    def submit(self, intent: OperatorOrderIntent) -> OperatorOrderResult:
        intent_id, risk_id = uuid4(), uuid4()
        state = self.runtime_state()
        if intent.lots <= 0 or intent.quantity <= 0:
            return self._deny(intent_id, ("INVALID_QUANTITY",))
        if not getattr(state, "can_enter", False) or getattr(state, "paused", False):
            return self._deny(intent_id, ("SESSION_ENTRY_BLOCKED",))
        if getattr(state, "is_halted", False):
            return self._deny(intent_id, ("SYSTEM_HALTED",))
        try:
            spec = self.references.resolve(intent.instrument_key, as_of=intent.requested_at)
        except InstrumentReferenceError as error:
            return self._deny(intent_id, (error.code,))
        reasons: list[str] = []
        if spec.option_type is None or spec.option_type.value != intent.option_type:
            reasons.append("OPTION_TYPE_MISMATCH")
        if str(spec.expiry) != intent.expiry or spec.strike != intent.strike:
            reasons.append("INSTRUMENT_SPEC_MISMATCH")
        if intent.quantity != Decimal(spec.lot_size * intent.lots):
            reasons.append("INVALID_LOT_QUANTITY")
        if not self.market_feed.data_fresh(
            intent.instrument_key, now=intent.requested_at, max_age_ms=self.max_quote_age_ms
        ):
            reasons.append("OPTION_QUOTE_STALE")
        mark = self.market_feed.latest_mark(intent.instrument_key)
        price = intent.requested_price if intent.order_type == "LIMIT" else mark
        if price is None or price <= 0:
            reasons.append("OPTION_PRICE_UNAVAILABLE")
        capital = (price or Decimal("0")) * intent.quantity
        if capital > Decimal(str(getattr(state, "available", "0"))):
            reasons.append("INSUFFICIENT_CAPITAL")
        if not self.broker.is_healthy():
            reasons.append("PAPER_BROKER_UNHEALTHY")
        if reasons:
            return self._deny(intent_id, tuple(reasons), risk_id=risk_id)
        decision = self.a04(intent, capital)
        if not decision.allowed or decision.token_id is None:
            return self._deny(
                intent_id,
                ("A04_DENY", *decision.reason_codes),
                risk_id=risk_id,
                a04_id=decision.decision_id,
            )
        request = OrderRequest(
            instrument_id=intent.instrument_key,
            side="BUY",
            quantity=intent.quantity,
            order_type=intent.order_type,
            limit_price=price,
            idempotency_key=str(intent.operator_action_id),
            intent_id=str(intent_id),
        )
        order = self.broker.submit_order(request, now=intent.requested_at)
        if order is None:
            return self._deny(
                intent_id,
                ("PAPER_BROKER_REJECTED",),
                risk_id=risk_id,
                a04_id=decision.decision_id,
            )
        assert price is not None
        self.broker.seed_fill(order.order_id, price, intent.quantity, now=intent.requested_at)
        fill_id, position_id = uuid4(), uuid4()
        self.runtime.handle_fill(
            str(position_id),
            price,
            intent.quantity,
            intent.requested_at,
            instrument_id=intent.instrument_key,
            lot_size=spec.lot_size,
            direction="BULLISH" if intent.option_type == "CE" else "BEARISH",
            origin=PositionOrigin.OPERATOR_MANUAL,
            managed_exit_mode=intent.managed_exit_mode,
            operator_action_id=str(intent.operator_action_id),
        )
        result = OperatorOrderResult(
            accepted=True,
            state=OperatorOrderState.FILLED,
            reason_codes=("RISK_ACCEPTED", "A04_AUTHORIZED", "PAPER_FILL_RECORDED"),
            order_intent_id=intent_id,
            risk_decision_id=risk_id,
            a04_decision_id=decision.decision_id,
            token_id=decision.token_id,
            paper_order_id=order.order_id,
            fill_id=fill_id,
            position_id=position_id,
        )
        self.evidence.append(
            {"operator_action_id": str(intent.operator_action_id), **result.model_dump(mode="json")}
        )
        return result

    def _deny(
        self,
        intent_id: UUID,
        reasons: tuple[str, ...],
        *,
        risk_id: UUID | None = None,
        a04_id: UUID | None = None,
    ) -> OperatorOrderResult:
        result = OperatorOrderResult(
            accepted=False,
            state=OperatorOrderState.REJECTED,
            reason_codes=reasons,
            order_intent_id=intent_id,
            risk_decision_id=risk_id,
            a04_decision_id=a04_id,
        )
        self.evidence.append(result.model_dump(mode="json"))
        return result


__all__ = [
    "A04OperatorDecision",
    "OperatorOrderIntent",
    "OperatorOrderResult",
    "OperatorOrderService",
    "OperatorOrderState",
]
