"""Approved SDK order boundary, separate from read-only market connectors.

Injected SDK must belong to an isolated, authenticated account session. This
adapter is not commissioned or connected to console routing yet.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

from ats.execution.external import ExternalIntent


class MT5ExecutionAdapter:
    def __init__(
        self,
        sdk: Any,
        *,
        expected_login: int,
        expected_server: str,
        broker_symbol: str,
        filling_mode: int,
        expected_mode: Literal["DEMO", "LIVE"] = "DEMO",
        normalize_tick: Callable[[int, str, datetime], datetime] | None = None,
    ) -> None:
        self._sdk = sdk
        self._login, self._server = expected_login, expected_server
        self._symbol, self._filling = broker_symbol, filling_mode
        self._normalize_tick = normalize_tick
        self._mode = expected_mode

    def submit(self, intent: ExternalIntent) -> dict[str, Any]:
        sdk = self._sdk
        account, terminal = sdk.account_info(), sdk.terminal_info()
        if (
            account is None
            or terminal is None
            or not terminal.connected
            or account.login != self._login
            or account.server != self._server
            or not account.trade_allowed
            or not terminal.trade_allowed
            or getattr(account, "trade_expert", None) is not True
            or getattr(terminal, "tradeapi_disabled", None) is not False
        ):
            return {"state": "REJECTED", "reason": "ACCOUNT_OR_TRADING_PERMISSION_INVALID"}
        if intent.broker_symbol != self._symbol or intent.expires_at <= datetime.now(UTC):
            return {"state": "REJECTED", "reason": "SYMBOL_OR_EXPIRY_INVALID"}
        mode = {
            sdk.ACCOUNT_TRADE_MODE_DEMO: "DEMO",
            sdk.ACCOUNT_TRADE_MODE_REAL: "LIVE",
        }.get(account.trade_mode, "UNKNOWN")
        if mode != self._mode:
            return {"state": "REJECTED", "reason": "ACCOUNT_MODE_CHANGED"}
        if self._filling not in {sdk.ORDER_FILLING_FOK, sdk.ORDER_FILLING_IOC}:
            return {"state": "REJECTED", "reason": "UNSUPPORTED_FILLING_POLICY"}
        tick, info = sdk.symbol_info_tick(self._symbol), sdk.symbol_info(self._symbol)
        if tick is None or info is None:
            return {"state": "REJECTED", "reason": "BROKER_METADATA_UNKNOWN"}
        now = datetime.now(UTC)
        try:
            stamp = (
                self._normalize_tick(tick.time_msc, self._server, now)
                if self._normalize_tick is not None
                else datetime.fromtimestamp(tick.time_msc / 1000, UTC)
            )
            age = (now - stamp).total_seconds()
        except (ValueError, TypeError, OverflowError):
            return {"state": "REJECTED", "reason": "BROKER_CLOCK_NOT_COMMISSIONED_OR_STALE"}
        if not 0 <= age <= 5:
            return {"state": "REJECTED", "reason": "BROKER_CLOCK_NOT_COMMISSIONED_OR_STALE"}
        try:
            bid, ask = Decimal(str(tick.bid)), Decimal(str(tick.ask))
            point, tick_size = Decimal(str(info.point)), Decimal(str(info.trade_tick_size))
            volume_min, volume_max, volume_step = (
                Decimal(str(info.volume_min)),
                Decimal(str(info.volume_max)),
                Decimal(str(info.volume_step)),
            )
            stops_level = Decimal(str(info.trade_stops_level))
            filling_flags = info.filling_mode
        except (ValueError, TypeError, AttributeError, InvalidOperation):
            return {"state": "REJECTED", "reason": "BROKER_METADATA_UNKNOWN"}
        if not all(
            value.is_finite() and value > 0
            for value in (bid, ask, point, tick_size, volume_min, volume_max, volume_step)
        ):
            return {"state": "REJECTED", "reason": "BROKER_METADATA_UNKNOWN"}
        filling_flag = (
            sdk.SYMBOL_FILLING_FOK
            if self._filling == sdk.ORDER_FILLING_FOK
            else sdk.SYMBOL_FILLING_IOC
        )
        if (
            not stops_level.is_finite()
            or stops_level < 0
            or not isinstance(filling_flags, int)
            or not filling_flags & filling_flag
        ):
            return {"state": "REJECTED", "reason": "BROKER_STOP_OR_FILLING_POLICY_INVALID"}
        price = ask if intent.side == "BUY" else bid
        if ask < bid or abs(price - intent.entry) > point * intent.max_deviation_points:
            return {"state": "REJECTED", "reason": "QUOTE_OUTSIDE_AUTHORIZED_DEVIATION"}
        valid = (
            intent.sl < price < intent.tp if intent.side == "BUY" else intent.tp < price < intent.sl
        )
        if not valid:
            return {"state": "REJECTED", "reason": "STOP_TARGET_GEOMETRY_CHANGED"}
        stop_distance, target_distance = (
            (bid - intent.sl, intent.tp - bid)
            if intent.side == "BUY"
            else (intent.sl - ask, ask - intent.tp)
        )
        if min(stop_distance, target_distance) < stops_level * point:
            return {"state": "REJECTED", "reason": "BROKER_STOP_DISTANCE_INVALID"}
        free_margin = Decimal(str(account.margin_free))
        if (
            not volume_min <= intent.volume <= volume_max
            or intent.volume % volume_step
            or any(value % tick_size for value in (intent.entry, intent.sl, intent.tp))
        ):
            return {"state": "REJECTED", "reason": "BROKER_GRID_MISMATCH"}
        order_type = sdk.ORDER_TYPE_BUY if intent.side == "BUY" else sdk.ORDER_TYPE_SELL
        profit = sdk.order_calc_profit(
            order_type, self._symbol, float(intent.volume), float(price), float(intent.sl)
        )
        margin = sdk.order_calc_margin(order_type, self._symbol, float(intent.volume), float(price))
        if profit is None or margin is None:
            return {"state": "REJECTED", "reason": "BROKER_RISK_OR_MARGIN_UNKNOWN"}
        loss, observed_margin = -Decimal(str(profit)), Decimal(str(margin))
        if (
            not loss.is_finite()
            or not observed_margin.is_finite()
            or loss <= 0
            or observed_margin <= 0
            or not free_margin.is_finite()
            or loss > intent.risk_cash
            or observed_margin > intent.margin_cash
            or observed_margin > free_margin
        ):
            return {"state": "REJECTED", "reason": "BROKER_RISK_OR_MARGIN_EXCEEDS_AUTHORITY"}
        request = {
            "action": sdk.TRADE_ACTION_DEAL,
            "symbol": self._symbol,
            "volume": float(intent.volume),
            "price": float(price),
            "type": order_type,
            "sl": float(intent.sl),
            "tp": float(intent.tp),
            "deviation": intent.max_deviation_points,
            "type_filling": self._filling,
            "type_time": sdk.ORDER_TIME_GTC,
            "comment": "ATS:" + hashlib.sha256(intent.idempotency.encode()).hexdigest()[:24],
        }
        check = sdk.order_check(request)
        if check is None or check.retcode != 0:
            return {"state": "REJECTED", "reason": "BROKER_PREFLIGHT_REJECTED"}
        result = sdk.order_send(request)
        if result is None:
            return {"state": "UNKNOWN", "reason": "BROKER_ACK_UNKNOWN"}
        accepted = {
            sdk.TRADE_RETCODE_DONE,
            sdk.TRADE_RETCODE_DONE_PARTIAL,
            sdk.TRADE_RETCODE_PLACED,
        }
        # Vendor timeout/connection errors cannot establish that no order was placed.
        rejected = {
            sdk.TRADE_RETCODE_REJECT,
            sdk.TRADE_RETCODE_INVALID,
            sdk.TRADE_RETCODE_INVALID_VOLUME,
            sdk.TRADE_RETCODE_INVALID_STOPS,
            sdk.TRADE_RETCODE_NO_MONEY,
            sdk.TRADE_RETCODE_TRADE_DISABLED,
        }
        state = (
            "ACCEPTED"
            if result.retcode in accepted
            else "REJECTED"
            if result.retcode in rejected
            else "UNKNOWN"
        )
        return {
            "state": state,
            "retcode": result.retcode,
            "broker_order_id": result.order,
            "broker_deal_id": result.deal,
            "fill_price": str(result.price),
            "fill_volume": str(result.volume),
            "commission": None,
            "swap": None,
        }

    def observed_state(self) -> dict[str, Any]:
        account = self._sdk.account_info()
        if account is None or account.login != self._login or account.server != self._server:
            raise ValueError("AUTHENTICATED_ACCOUNT_MISMATCH")
        # Account-wide exposure is required: a filtered XAUUSD snapshot can hide risk.
        positions = self._sdk.positions_get()
        orders = self._sdk.orders_get()
        if positions is None or orders is None:
            raise ValueError("BROKER_STATE_UNKNOWN")
        return {
            "positions": [p._asdict() for p in positions],
            "orders": [o._asdict() for o in orders],
        }
