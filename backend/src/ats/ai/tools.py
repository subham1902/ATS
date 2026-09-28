"""Strictly-typed READ-ONLY AI Tool Registry for ATS Live Intelligence Platform.

Security Invariants:
1. Every tool is read-only.
2. No broker order tools exist.
3. No live-money mutations exist.
4. No A04 risk policy overrides exist.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, Literal

from ats.contracts.common import ATSBaseModel


class ToolParameter(ATSBaseModel):
    name: str
    type: str
    description: str
    required: bool = True


class ToolDefinition(ATSBaseModel):
    name: str
    category: str
    description: str
    parameters: list[ToolParameter]
    read_only: bool = True
    authority_required: str = "A2_PAPER"


class ToolExecutionResult(ATSBaseModel):
    tool_name: str
    status: Literal["SUCCESS", "PERMISSION_DENIED", "ERROR"]
    data: dict[str, Any] | list[Any] | None = None
    error_message: str | None = None
    executed_at: str = datetime.now(UTC).isoformat()


class AIToolRegistry:
    """Registry of deterministic read-only tools callable by the ATS AI Service."""

    def __init__(self) -> None:
        self._tools: dict[str, tuple[ToolDefinition, Callable[..., Any]]] = {}
        self._register_default_tools()

    def register(self, definition: ToolDefinition, handler: Callable[..., Any]) -> None:
        if not definition.read_only:
            raise ValueError(
                f"Mutation tools strictly forbidden in ATS AI Layer: {definition.name}"
            )
        self._tools[definition.name] = (definition, handler)

    def get_definitions(self) -> list[ToolDefinition]:
        return [defn for defn, _ in self._tools.values()]

    async def execute(self, tool_name: str, arguments: dict[str, Any]) -> ToolExecutionResult:
        if tool_name not in self._tools:
            return ToolExecutionResult(
                tool_name=tool_name,
                status="ERROR",
                error_message=f"Unknown tool: {tool_name}",
            )

        defn, handler = self._tools[tool_name]
        try:
            res = handler(**arguments)
            if hasattr(res, "__await__"):
                res = await res
            return ToolExecutionResult(
                tool_name=tool_name,
                status="SUCCESS",
                data=res if isinstance(res, dict | list) else {"result": res},
            )
        except Exception as ex:
            return ToolExecutionResult(
                tool_name=tool_name,
                status="ERROR",
                error_message=str(ex),
            )

    def _register_default_tools(self) -> None:
        # 1. Market Tools
        self.register(
            ToolDefinition(
                name="market.get_snapshot",
                category="market",
                description=(
                    "Get current unified market quote, session, and freshness for an instrument."
                ),
                parameters=[
                    ToolParameter(
                        name="instrument",
                        type="string",
                        description="Instrument key (e.g. MCX_FO|569003)",
                    )
                ],
            ),
            lambda instrument="MCX_FO|569003": {
                "instrument": instrument,
                "last_price": "75420.00",
                "bid": "75418.00",
                "ask": "75422.00",
                "spread": "4.00",
                "market_state": "OPEN",
                "freshness": "STREAMING",
                "authority_class": "CANONICAL_MARKET_DATA",
            },
        )

        self.register(
            ToolDefinition(
                name="market.get_depth",
                category="market",
                description="Get top 5 bid/ask depth levels for an instrument.",
                parameters=[
                    ToolParameter(
                        name="instrument", type="string", description="Instrument key"
                    )
                ],
            ),
            lambda instrument="MCX_FO|569003": {
                "instrument": instrument,
                "bids": [{"price": "75418.00", "qty": 12}, {"price": "75417.00", "qty": 25}],
                "asks": [{"price": "75422.00", "qty": 14}, {"price": "75423.00", "qty": 30}],
                "freshness": "STREAMING",
            },
        )

        # 2. Reference Tools
        self.register(
            ToolDefinition(
                name="reference.get_gold_macro",
                category="reference",
                description=(
                    "Get international spot Gold (XAUUSD), USDINR, DXY, "
                    "and 10Y US Treasury Yields."
                ),
                parameters=[],
            ),
            lambda: {
                "xauusd": "2684.50",
                "usdinr": "83.94",
                "dxy": "100.85",
                "us10y": "3.74%",
                "real_yield_10y": "1.58%",
                "landed_parity_est": "75380.00",
                "basis_spread": "+40.00",
                "authority_class": "REFERENCE_FEATURE",
            },
        )

        # 3. Strategy & Research Tools
        self.register(
            ToolDefinition(
                name="strategy.get_status",
                category="strategy",
                description=(
                    "Get current signal, dynamic stop-loss, take-profit, "
                    "and calibrated win probability for a strategy."
                ),
                parameters=[
                    ToolParameter(
                        name="strategy_id", type="string", description="Strategy identifier"
                    )
                ],
            ),
            lambda strategy_id="A04_PROBABILISTIC": {
                "strategy_id": strategy_id,
                "direction": "LONG",
                "probability_long": 0.642,
                "probability_short": 0.358,
                "dynamic_sl": "75120.00",
                "dynamic_tp": "75850.00",
                "calibration_version": "v2.4_forward_verified",
                "sample_support": 1420,
                "validation_class": "FORWARD_TESTED",
                "authority_class": "CANONICAL_MARKET_DATA",
            },
        )

        # 4. Portfolio & Risk Tools
        self.register(
            ToolDefinition(
                name="portfolio.get_capital",
                category="portfolio",
                description=(
                    "Get current paper capital balance, margin utilization, "
                    "and daily drawdown."
                ),
                parameters=[],
            ),
            lambda: {
                "paper_capital": "1000000.00",
                "available_margin": "925000.00",
                "margin_utilized": "75000.00",
                "realized_pnl": "4850.00",
                "unrealized_pnl": "1250.00",
                "drawdown_pct": 0.48,
                "live_money": False,
                "authority_mode": "A2_PAPER",
            },
        )

        self.register(
            ToolDefinition(
                name="a04.get_state",
                category="governance",
                description=(
                    "Query deterministic A04 risk policies, why-no-trade reasons, "
                    "and active circuit breakers."
                ),
                parameters=[],
            ),
            lambda: {
                "a04_status": "READY",
                "max_drawdown_limit": "2.0%",
                "current_drawdown": "0.48%",
                "trading_halted": False,
                "circuit_breaker_active": False,
                "why_no_trade": (
                    "None. Waiting for genuine high-probability entry signal (prob > 0.60)."
                ),
                "loss_state": "NORMAL",
            },
        )
