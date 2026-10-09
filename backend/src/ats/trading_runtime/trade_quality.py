"""Causal, versioned trade-path diagnostics. Advisories confer no exit authority."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ats.market.observations import MarketObservation

QUALITY_VERSION = "OBSERVED-QUOTE-QUALITY-V1"


class TradeOpening(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)
    execution_id: str = Field(min_length=1)
    account_id: str = Field(min_length=1)
    strategy_id: str = Field(pattern=r"^XAU-[0-9]{3,}$")
    strategy_version: int = Field(ge=1)
    mode: Literal["PAPER", "DEMO", "LIVE"]
    signal_id: str = Field(min_length=1)
    broker_symbol: str = Field(min_length=1)
    side: Literal["LONG", "SHORT"]
    time: datetime
    signal_price: Decimal = Field(gt=0)
    entry: Decimal = Field(gt=0)
    initial_sl: Decimal = Field(gt=0)
    initial_tp: Decimal | None = Field(default=None, gt=0)
    quantity: Decimal = Field(gt=0)
    spread_at_entry: Decimal | None = Field(default=None, ge=0)
    commission_cash: Decimal | None = Field(default=None, ge=0)
    max_observation_gap_seconds: int = Field(default=5, ge=1, le=300)

    @model_validator(mode="after")
    def validate_opening(self) -> TradeOpening:
        if self.time.tzinfo is None:
            raise ValueError("AWARE_TRADE_TIME_REQUIRED")
        if not (
            self.initial_sl < self.entry if self.side == "LONG" else self.initial_sl > self.entry
        ):
            raise ValueError("INITIAL_RISK_REQUIRED")
        if self.initial_tp is not None and not (
            self.initial_tp > self.entry if self.side == "LONG" else self.initial_tp < self.entry
        ):
            raise ValueError("INVALID_TARGET")
        return self


class TradePath:
    def __init__(self, opening: TradeOpening) -> None:
        self.opening = opening
        self.risk = abs(opening.entry - opening.initial_sl)
        self.sign = Decimal(1) if opening.side == "LONG" else Decimal(-1)
        self.mfe = self.mae = self.early_mae = Decimal(0)
        self.current: Decimal | None = None
        self.last_time = opening.time
        self.samples = 0
        self.complete = True
        self.closed = False
        self.realized: Decimal | None = None
        self.exit_source: Literal["OPERATOR", "STRATEGY", "BROKER"] | None = None
        self.shadow_exit: Decimal | None = None

    def observe(self, observation: MarketObservation) -> None:
        if observation.broker_symbol != self.opening.broker_symbol:
            raise ValueError("TRADE_QUOTE_SYMBOL_MISMATCH")
        if (
            observation.timestamp < self.last_time
            or observation.timestamp > observation.received_at
        ):
            raise ValueError("NONCAUSAL_TRADE_OBSERVATION")
        if observation.timestamp == self.last_time and self.samples:
            raise ValueError("DUPLICATE_TRADE_OBSERVATION")
        gap = (observation.timestamp - self.last_time).total_seconds()
        price = observation.bid if self.opening.side == "LONG" else observation.ask
        if price is None:
            self.complete = False
            return
        if gap > self.opening.max_observation_gap_seconds:
            self.complete = False
        excursion = self.sign * (price - self.opening.entry) / self.risk
        self.last_time = observation.timestamp
        if self.closed:
            # Freeze actual evidence; only an operator exit creates a hypothetical path.
            if self.exit_source == "OPERATOR" and self.shadow_exit is None:
                hit_stop = self.sign * (price - self.opening.initial_sl) <= 0
                tp = self.opening.initial_tp
                hit_target = tp is not None and self.sign * (price - tp) >= 0
                if hit_stop or hit_target:
                    self.shadow_exit = excursion
            return
        self.current = excursion
        self.mfe, self.mae = max(self.mfe, excursion), min(self.mae, excursion)
        if (observation.timestamp - self.opening.time).total_seconds() <= 300:
            self.early_mae = min(self.early_mae, excursion)
        self.samples += 1

    def close(
        self, *, price: Decimal, time: datetime, source: Literal["OPERATOR", "STRATEGY", "BROKER"]
    ) -> None:
        if (
            self.closed
            or not price.is_finite()
            or price <= 0
            or time.tzinfo is None
            or time < self.last_time
        ):
            raise ValueError("INVALID_OR_DUPLICATE_TRADE_EXIT")
        if (time - self.last_time).total_seconds() > self.opening.max_observation_gap_seconds:
            self.complete = False
        self.realized = self.sign * (price - self.opening.entry) / self.risk
        self.closed, self.exit_source, self.last_time = True, source, time

    def report(self) -> dict[str, Any]:
        current = self.realized if self.closed else self.current
        giveback = (self.mfe - current) / self.mfe if self.mfe > 0 and current is not None else None
        capture = (
            self.realized / self.mfe
            if self.closed and self.mfe > 0 and self.realized is not None
            else None
        )
        duration = (self.last_time - self.opening.time).total_seconds()
        entry = exit_label = diagnosis = "UNKNOWN"
        if self.complete and self.samples >= 5 and duration >= 300:
            drift = self.sign * (self.opening.entry - self.opening.signal_price) / self.risk
            if (
                self.opening.spread_at_entry is not None
                and self.opening.spread_at_entry / self.risk > Decimal(".2")
            ):
                entry = "HIGH_SPREAD_ENTRY"
            elif drift > Decimal(".25"):
                entry = "CHASED_ENTRY"
            else:
                entry = "GOOD_ENTRY" if self.early_mae >= Decimal("-.5") else "POOR_ENTRY"
            if self.closed and capture is not None:
                exit_label = (
                    "HIGH_PROFIT_GIVEBACK"
                    if self.mfe >= 1 and capture < Decimal(".6")
                    else "GOOD_EXIT"
                )
                diagnosis = ("GOOD_ENTRY" if entry == "GOOD_ENTRY" else "BAD_ENTRY") + (
                    "_GOOD_EXIT" if exit_label == "GOOD_EXIT" else "_BAD_EXIT"
                )
        attention = (
            self.mfe >= 1 and giveback is not None and giveback >= Decimal(".3") and not self.closed
        )
        return {
            **self.opening.model_dump(mode="json"),
            "quality_version": QUALITY_VERSION,
            "samples": self.samples,
            "path_complete": self.complete,
            "metric_basis": "GROSS_PRICE_R_OBSERVED_QUOTES",
            "MFE_R": str(self.mfe) if self.samples else None,
            "MAE_R": str(self.mae) if self.samples else None,
            "current_R": str(current) if current is not None else None,
            "realized_R": str(self.realized) if self.realized is not None else None,
            "net_realized_R": str(
                self.realized - self.opening.commission_cash / (self.risk * self.opening.quantity)
            )
            if self.realized is not None and self.opening.commission_cash is not None
            else None,
            "giveback_fraction": str(giveback) if giveback is not None else None,
            "MFE_capture_ratio": str(capture) if capture is not None else None,
            "entry_quality": entry,
            "exit_quality": exit_label,
            "diagnosis": diagnosis,
            "closed": self.closed,
            "exit_source": self.exit_source,
            "exit_watch": "MANUAL_EXIT_REVIEW" if attention else "NO_ADVISORY",
            "financial_authority": "NONE",
            "shadow_method": "STATIC_INITIAL_SL_TP_OBSERVED_QUOTES_NOT_TRAILING_REPLAY",
            "shadow_exit_R": str(self.shadow_exit) if self.shadow_exit is not None else None,
            "human_minus_shadow_R": str(self.realized - self.shadow_exit)
            if self.exit_source == "OPERATOR"
            and self.realized is not None
            and self.shadow_exit is not None
            else None,
        }
