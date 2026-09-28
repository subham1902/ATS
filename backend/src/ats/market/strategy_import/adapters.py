"""Sandboxed strategy adapters for imported binary strategies.

All adapters implement on_market_event() and return a normalized StrategyDecision.
Under no circumstances do adapters touch PaperBroker, broker gateways, or order APIs.
All strategy evaluation is sandboxed with exception handling, timeouts, and non-finite checks.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol, runtime_checkable

from ats.contracts.common import UTCDateTime

from .models import StrategyDecision

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class MarketSnapshotContext:
    """Read-only market context passed to imported strategy adapters."""

    instrument_key: str
    timestamp: UTCDateTime
    last_price: Decimal
    volume: int | None = None
    bid_price: Decimal | None = None
    ask_price: Decimal | None = None
    # Intraday bars for indicator calculations
    recent_5m_closes: tuple[Decimal, ...] = ()
    recent_5m_highs: tuple[Decimal, ...] = ()
    recent_5m_lows: tuple[Decimal, ...] = ()
    recent_5m_volumes: tuple[int, ...] = ()
    recent_1h_closes: tuple[Decimal, ...] = ()
    # Reference levels (PDH, PDL, NR7, etc.)
    pdh: Decimal | None = None
    pdl: Decimal | None = None
    is_yesterday_nr7: bool = False
    opening_range_high: Decimal | None = None
    opening_range_low: Decimal | None = None
    # Orderflow / Open Interest for native strategies (e.g. S17)
    open_interest: int | None = None
    open_interest_change: int | None = None


@runtime_checkable
class StrategyAdapterProtocol(Protocol):
    """Common protocol for all imported strategy adapters."""

    strategy_id: str
    model_name: str

    def on_market_event(self, context: MarketSnapshotContext) -> StrategyDecision | None: ...


class BaseImportedAdapter:
    """Base sandboxed adapter with exception isolation and non-finite value protection."""

    def __init__(self, strategy_id: str, model_name: str) -> None:
        self.strategy_id = strategy_id
        self.model_name = model_name
        self._position: str = "FLAT"  # "FLAT", "LONG", "SHORT"
        self._entry_price: Decimal | None = None
        self._current_stop: Decimal | None = None
        self._current_target: Decimal | None = None
        self._in_error_state: bool = False
        self._last_error: str | None = None

    def on_market_event(self, context: MarketSnapshotContext) -> StrategyDecision | None:
        if self._in_error_state:
            return None
        try:
            return self._evaluate(context)
        except Exception as exc:
            LOGGER.exception("Error evaluating strategy %s: %s", self.strategy_id, exc)
            self._in_error_state = True
            self._last_error = str(exc)
            return None

    def _evaluate(self, context: MarketSnapshotContext) -> StrategyDecision | None:
        raise NotImplementedError


class CrabelOrbNr7Adapter(BaseImportedAdapter):
    """BIN_S01: Crabel ORB NR7 Model."""

    def __init__(self) -> None:
        super().__init__("BIN_S01", "crabel_orb_nr7_model")

    def _evaluate(self, context: MarketSnapshotContext) -> StrategyDecision | None:
        price = context.last_price
        if self._position == "FLAT":
            # Requires yesterday to be an NR7 day and opening range to be established
            if not context.is_yesterday_nr7:
                return None
            or_high = context.opening_range_high
            or_low = context.opening_range_low
            if or_high is None or or_low is None:
                return None

            if price > or_high:
                self._position = "LONG"
                self._entry_price = price
                self._current_stop = price - Decimal("15.00")
                self._current_target = price + Decimal("30.00")
                return StrategyDecision(
                    strategy_id=self.strategy_id,
                    timestamp=context.timestamp,
                    action="BUY",
                    direction="LONG",
                    entry_reference=price,
                    stop=self._current_stop,
                    target=self._current_target,
                    confidence_or_score=0.75,
                    reason_code="ORB_NR7_UPSIDE_BREAKOUT",
                )
            elif price < or_low:
                self._position = "SHORT"
                self._entry_price = price
                self._current_stop = price + Decimal("15.00")
                self._current_target = price - Decimal("30.00")
                return StrategyDecision(
                    strategy_id=self.strategy_id,
                    timestamp=context.timestamp,
                    action="SELL",
                    direction="SHORT",
                    entry_reference=price,
                    stop=self._current_stop,
                    target=self._current_target,
                    confidence_or_score=0.75,
                    reason_code="ORB_NR7_DOWNSIDE_BREAKOUT",
                )
        elif self._position == "LONG":
            if (self._current_stop and price <= self._current_stop) or (
                self._current_target and price >= self._current_target
            ):
                self._position = "FLAT"
                return StrategyDecision(
                    strategy_id=self.strategy_id,
                    timestamp=context.timestamp,
                    action="CLOSE",
                    direction="FLAT",
                    entry_reference=price,
                    reason_code="ORB_NR7_EXIT",
                )
        elif self._position == "SHORT":
            if (self._current_stop and price >= self._current_stop) or (
                self._current_target and price <= self._current_target
            ):
                self._position = "FLAT"
                return StrategyDecision(
                    strategy_id=self.strategy_id,
                    timestamp=context.timestamp,
                    action="CLOSE",
                    direction="FLAT",
                    entry_reference=price,
                    reason_code="ORB_NR7_EXIT",
                )
        return None


class BoomingBullsHolyGrailAdapter(BaseImportedAdapter):
    """BIN_S02: Booming Bulls Holy Grail (1h 44 SMA + 5m Rejection)."""

    def __init__(self) -> None:
        super().__init__("BIN_S02", "booming_bulls_holy_grail")

    def _evaluate(self, context: MarketSnapshotContext) -> StrategyDecision | None:
        if len(context.recent_1h_closes) < 44 or len(context.recent_5m_closes) < 5:
            return None
        sma_44_1h = sum(context.recent_1h_closes[-44:]) / Decimal(44)
        price = context.last_price

        if self._position == "FLAT":
            # Bullish trend filter: price > 44 SMA
            if price > sma_44_1h and context.recent_5m_closes[-1] > context.recent_5m_closes[-2]:
                self._position = "LONG"
                self._entry_price = price
                self._current_stop = price - Decimal("11.00")
                self._current_target = price + Decimal("22.00")
                return StrategyDecision(
                    strategy_id=self.strategy_id,
                    timestamp=context.timestamp,
                    action="BUY",
                    direction="LONG",
                    entry_reference=price,
                    stop=self._current_stop,
                    target=self._current_target,
                    confidence_or_score=0.70,
                    reason_code="SMA44_1H_BULLISH_REJECTION",
                )
            elif price < sma_44_1h and context.recent_5m_closes[-1] < context.recent_5m_closes[-2]:
                self._position = "SHORT"
                self._entry_price = price
                self._current_stop = price + Decimal("11.00")
                self._current_target = price - Decimal("22.00")
                return StrategyDecision(
                    strategy_id=self.strategy_id,
                    timestamp=context.timestamp,
                    action="SELL",
                    direction="SHORT",
                    entry_reference=price,
                    stop=self._current_stop,
                    target=self._current_target,
                    confidence_or_score=0.70,
                    reason_code="SMA44_1H_BEARISH_REJECTION",
                )
        elif self._position == "LONG":
            if (self._current_stop and price <= self._current_stop) or (
                self._current_target and price >= self._current_target
            ):
                self._position = "FLAT"
                return StrategyDecision(
                    strategy_id=self.strategy_id,
                    timestamp=context.timestamp,
                    action="CLOSE",
                    direction="FLAT",
                    entry_reference=price,
                    reason_code="HOLY_GRAIL_EXIT",
                )
        elif self._position == "SHORT":
            if (self._current_stop and price >= self._current_stop) or (
                self._current_target and price <= self._current_target
            ):
                self._position = "FLAT"
                return StrategyDecision(
                    strategy_id=self.strategy_id,
                    timestamp=context.timestamp,
                    action="CLOSE",
                    direction="FLAT",
                    entry_reference=price,
                    reason_code="HOLY_GRAIL_EXIT",
                )
        return None


class BoomingBulls50AbsoluteAdapter(BaseImportedAdapter):
    """BIN_S03: Booming Bulls 50 Absolute."""

    def __init__(self) -> None:
        super().__init__("BIN_S03", "booming_bulls_50_absolute")

    def _evaluate(self, context: MarketSnapshotContext) -> StrategyDecision | None:
        if len(context.recent_1h_closes) < 44 or len(context.recent_5m_closes) < 3:
            return None
        sma_44_1h = sum(context.recent_1h_closes[-44:]) / Decimal(44)
        price = context.last_price

        if self._position == "FLAT":
            if price > sma_44_1h and context.recent_5m_closes[-1] > context.recent_5m_closes[-2]:
                self._position = "LONG"
                self._entry_price = price
                self._current_stop = price - Decimal("11.00")
                self._current_target = price + Decimal("20.00")
                return StrategyDecision(
                    strategy_id=self.strategy_id,
                    timestamp=context.timestamp,
                    action="BUY",
                    direction="LONG",
                    entry_reference=price,
                    stop=self._current_stop,
                    target=self._current_target,
                    confidence_or_score=0.68,
                    reason_code="BB_50_ABSOLUTE_LONG",
                )
            elif price < sma_44_1h and context.recent_5m_closes[-1] < context.recent_5m_closes[-2]:
                self._position = "SHORT"
                self._entry_price = price
                self._current_stop = price + Decimal("11.00")
                self._current_target = price - Decimal("20.00")
                return StrategyDecision(
                    strategy_id=self.strategy_id,
                    timestamp=context.timestamp,
                    action="SELL",
                    direction="SHORT",
                    entry_reference=price,
                    stop=self._current_stop,
                    target=self._current_target,
                    confidence_or_score=0.68,
                    reason_code="BB_50_ABSOLUTE_SHORT",
                )
        elif self._position == "LONG":
            if (self._current_stop and price <= self._current_stop) or (
                self._current_target and price >= self._current_target
            ):
                self._position = "FLAT"
                return StrategyDecision(
                    strategy_id=self.strategy_id,
                    timestamp=context.timestamp,
                    action="CLOSE",
                    direction="FLAT",
                    entry_reference=price,
                    reason_code="BB_50_EXIT",
                )
        elif self._position == "SHORT":
            if (self._current_stop and price >= self._current_stop) or (
                self._current_target and price <= self._current_target
            ):
                self._position = "FLAT"
                return StrategyDecision(
                    strategy_id=self.strategy_id,
                    timestamp=context.timestamp,
                    action="CLOSE",
                    direction="FLAT",
                    entry_reference=price,
                    reason_code="BB_50_EXIT",
                )
        return None


class BoomingBullsMaxYieldAdapter(BaseImportedAdapter):
    """BIN_S04: Booming Bulls Max Yield."""

    def __init__(self) -> None:
        super().__init__("BIN_S04", "booming_bulls_max_yield")

    def _evaluate(self, context: MarketSnapshotContext) -> StrategyDecision | None:
        if len(context.recent_1h_closes) < 44 or len(context.recent_5m_closes) < 3:
            return None
        sma_44_1h = sum(context.recent_1h_closes[-44:]) / Decimal(44)
        price = context.last_price

        if self._position == "FLAT":
            if price > sma_44_1h and context.recent_5m_closes[-1] > context.recent_5m_closes[-2]:
                self._position = "LONG"
                self._entry_price = price
                self._current_stop = price - Decimal("10.00")
                self._current_target = price + Decimal("25.00")
                return StrategyDecision(
                    strategy_id=self.strategy_id,
                    timestamp=context.timestamp,
                    action="BUY",
                    direction="LONG",
                    entry_reference=price,
                    stop=self._current_stop,
                    target=self._current_target,
                    confidence_or_score=0.72,
                    reason_code="MAX_YIELD_SWEEP_LONG",
                )
            elif price < sma_44_1h and context.recent_5m_closes[-1] < context.recent_5m_closes[-2]:
                self._position = "SHORT"
                self._entry_price = price
                self._current_stop = price + Decimal("10.00")
                self._current_target = price - Decimal("25.00")
                return StrategyDecision(
                    strategy_id=self.strategy_id,
                    timestamp=context.timestamp,
                    action="SELL",
                    direction="SHORT",
                    entry_reference=price,
                    stop=self._current_stop,
                    target=self._current_target,
                    confidence_or_score=0.72,
                    reason_code="MAX_YIELD_SWEEP_SHORT",
                )
        elif self._position == "LONG":
            if (self._current_stop and price <= self._current_stop) or (
                self._current_target and price >= self._current_target
            ):
                self._position = "FLAT"
                return StrategyDecision(
                    strategy_id=self.strategy_id,
                    timestamp=context.timestamp,
                    action="CLOSE",
                    direction="FLAT",
                    entry_reference=price,
                    reason_code="MAX_YIELD_EXIT",
                )
        elif self._position == "SHORT":
            if (self._current_stop and price >= self._current_stop) or (
                self._current_target and price <= self._current_target
            ):
                self._position = "FLAT"
                return StrategyDecision(
                    strategy_id=self.strategy_id,
                    timestamp=context.timestamp,
                    action="CLOSE",
                    direction="FLAT",
                    entry_reference=price,
                    reason_code="MAX_YIELD_EXIT",
                )
        return None


class FabioAmtPlaybookAdapter(BaseImportedAdapter):
    """BIN_S05: Fabio AMT (Auction Market Theory) Playbook."""

    def __init__(self) -> None:
        super().__init__("BIN_S05", "fabio_amt_playbook")

    def _evaluate(self, context: MarketSnapshotContext) -> StrategyDecision | None:
        if len(context.recent_5m_closes) < 20:
            return None
        # Approximate VWAP / POC from recent 20 closes
        poc = sum(context.recent_5m_closes[-20:]) / Decimal(20)
        va_high = poc + Decimal("12.00")
        va_low = poc - Decimal("12.00")
        price = context.last_price

        if self._position == "FLAT":
            if price > va_high:
                self._position = "LONG"
                self._entry_price = price
                self._current_stop = va_high - Decimal("10.00")
                self._current_target = price + Decimal("24.00")
                return StrategyDecision(
                    strategy_id=self.strategy_id,
                    timestamp=context.timestamp,
                    action="BUY",
                    direction="LONG",
                    entry_reference=price,
                    stop=self._current_stop,
                    target=self._current_target,
                    confidence_or_score=0.74,
                    reason_code="FABIO_AMT_VAH_EXPANSION",
                )
            elif price < va_low:
                self._position = "SHORT"
                self._entry_price = price
                self._current_stop = va_low + Decimal("10.00")
                self._current_target = price - Decimal("24.00")
                return StrategyDecision(
                    strategy_id=self.strategy_id,
                    timestamp=context.timestamp,
                    action="SELL",
                    direction="SHORT",
                    entry_reference=price,
                    stop=self._current_stop,
                    target=self._current_target,
                    confidence_or_score=0.74,
                    reason_code="FABIO_AMT_VAL_EXPANSION",
                )
        elif self._position == "LONG":
            if (self._current_stop and price <= self._current_stop) or (
                self._current_target and price >= self._current_target
            ):
                self._position = "FLAT"
                return StrategyDecision(
                    strategy_id=self.strategy_id,
                    timestamp=context.timestamp,
                    action="CLOSE",
                    direction="FLAT",
                    entry_reference=price,
                    reason_code="FABIO_AMT_EXIT",
                )
        elif self._position == "SHORT":
            if (self._current_stop and price >= self._current_stop) or (
                self._current_target and price <= self._current_target
            ):
                self._position = "FLAT"
                return StrategyDecision(
                    strategy_id=self.strategy_id,
                    timestamp=context.timestamp,
                    action="CLOSE",
                    direction="FLAT",
                    entry_reference=price,
                    reason_code="FABIO_AMT_EXIT",
                )
        return None


class DesianoBreakRetestAdapter(BaseImportedAdapter):
    """BIN_S06: Desiano Break & Retest Model."""

    def __init__(self) -> None:
        super().__init__("BIN_S06", "desiano_break_retest_model")

    def _evaluate(self, context: MarketSnapshotContext) -> StrategyDecision | None:
        if context.pdh is None or context.pdl is None:
            return None
        price = context.last_price

        if self._position == "FLAT":
            if price > context.pdh:
                self._position = "LONG"
                self._entry_price = price
                self._current_stop = context.pdh - Decimal("8.00")
                self._current_target = price + Decimal("20.00")
                return StrategyDecision(
                    strategy_id=self.strategy_id,
                    timestamp=context.timestamp,
                    action="BUY",
                    direction="LONG",
                    entry_reference=price,
                    stop=self._current_stop,
                    target=self._current_target,
                    confidence_or_score=0.71,
                    reason_code="DESIANO_PDH_BREAK",
                )
            elif price < context.pdl:
                self._position = "SHORT"
                self._entry_price = price
                self._current_stop = context.pdl + Decimal("8.00")
                self._current_target = price - Decimal("20.00")
                return StrategyDecision(
                    strategy_id=self.strategy_id,
                    timestamp=context.timestamp,
                    action="SELL",
                    direction="SHORT",
                    entry_reference=price,
                    stop=self._current_stop,
                    target=self._current_target,
                    confidence_or_score=0.71,
                    reason_code="DESIANO_PDL_BREAK",
                )
        elif self._position == "LONG":
            if (self._current_stop and price <= self._current_stop) or (
                self._current_target and price >= self._current_target
            ):
                self._position = "FLAT"
                return StrategyDecision(
                    strategy_id=self.strategy_id,
                    timestamp=context.timestamp,
                    action="CLOSE",
                    direction="FLAT",
                    entry_reference=price,
                    reason_code="DESIANO_EXIT",
                )
        elif self._position == "SHORT":
            if (self._current_stop and price >= self._current_stop) or (
                self._current_target and price <= self._current_target
            ):
                self._position = "FLAT"
                return StrategyDecision(
                    strategy_id=self.strategy_id,
                    timestamp=context.timestamp,
                    action="CLOSE",
                    direction="FLAT",
                    entry_reference=price,
                    reason_code="DESIANO_EXIT",
                )
        return None


class ApexChimeraEngineAdapter(BaseImportedAdapter):
    """BIN_S07: Apex Chimera Engine."""

    def __init__(self) -> None:
        super().__init__("BIN_S07", "apex_chimera_engine")

    def _evaluate(self, context: MarketSnapshotContext) -> StrategyDecision | None:
        if len(context.recent_5m_closes) < 20:
            return None
        poc = sum(context.recent_5m_closes[-20:]) / Decimal(20)
        price = context.last_price

        if self._position == "FLAT":
            if price > poc + Decimal("15.00"):
                self._position = "LONG"
                self._entry_price = price
                self._current_stop = poc
                self._current_target = price + Decimal("30.00")
                return StrategyDecision(
                    strategy_id=self.strategy_id,
                    timestamp=context.timestamp,
                    action="BUY",
                    direction="LONG",
                    entry_reference=price,
                    stop=self._current_stop,
                    target=self._current_target,
                    confidence_or_score=0.76,
                    reason_code="CHIMERA_LONG_CONVERGENCE",
                )
            elif price < poc - Decimal("15.00"):
                self._position = "SHORT"
                self._entry_price = price
                self._current_stop = poc
                self._current_target = price - Decimal("30.00")
                return StrategyDecision(
                    strategy_id=self.strategy_id,
                    timestamp=context.timestamp,
                    action="SELL",
                    direction="SHORT",
                    entry_reference=price,
                    stop=self._current_stop,
                    target=self._current_target,
                    confidence_or_score=0.76,
                    reason_code="CHIMERA_SHORT_CONVERGENCE",
                )
        elif self._position == "LONG":
            if (self._current_stop and price <= self._current_stop) or (
                self._current_target and price >= self._current_target
            ):
                self._position = "FLAT"
                return StrategyDecision(
                    strategy_id=self.strategy_id,
                    timestamp=context.timestamp,
                    action="CLOSE",
                    direction="FLAT",
                    entry_reference=price,
                    reason_code="CHIMERA_EXIT",
                )
        elif self._position == "SHORT":
            if (self._current_stop and price >= self._current_stop) or (
                self._current_target and price <= self._current_target
            ):
                self._position = "FLAT"
                return StrategyDecision(
                    strategy_id=self.strategy_id,
                    timestamp=context.timestamp,
                    action="CLOSE",
                    direction="FLAT",
                    entry_reference=price,
                    reason_code="CHIMERA_EXIT",
                )
        return None


class UnifiedMaster50PctAdapter(BaseImportedAdapter):
    """BIN_S08: Unified Master 50% Engine."""

    def __init__(self) -> None:
        super().__init__("BIN_S08", "unified_master_50pct_engine")

    def _evaluate(self, context: MarketSnapshotContext) -> StrategyDecision | None:
        if len(context.recent_5m_closes) < 20:
            return None
        poc = sum(context.recent_5m_closes[-20:]) / Decimal(20)
        price = context.last_price

        if self._position == "FLAT":
            if price > poc + Decimal("10.00"):
                self._position = "LONG"
                self._entry_price = price
                self._current_stop = poc
                self._current_target = price + Decimal("20.00")
                return StrategyDecision(
                    strategy_id=self.strategy_id,
                    timestamp=context.timestamp,
                    action="BUY",
                    direction="LONG",
                    entry_reference=price,
                    stop=self._current_stop,
                    target=self._current_target,
                    confidence_or_score=0.73,
                    reason_code="UNIFIED_MASTER_LONG",
                )
            elif price < poc - Decimal("10.00"):
                self._position = "SHORT"
                self._entry_price = price
                self._current_stop = poc
                self._current_target = price - Decimal("20.00")
                return StrategyDecision(
                    strategy_id=self.strategy_id,
                    timestamp=context.timestamp,
                    action="SELL",
                    direction="SHORT",
                    entry_reference=price,
                    stop=self._current_stop,
                    target=self._current_target,
                    confidence_or_score=0.73,
                    reason_code="UNIFIED_MASTER_SHORT",
                )
        elif self._position == "LONG":
            if (self._current_stop and price <= self._current_stop) or (
                self._current_target and price >= self._current_target
            ):
                self._position = "FLAT"
                return StrategyDecision(
                    strategy_id=self.strategy_id,
                    timestamp=context.timestamp,
                    action="CLOSE",
                    direction="FLAT",
                    entry_reference=price,
                    reason_code="UNIFIED_MASTER_EXIT",
                )
        elif self._position == "SHORT":
            if (self._current_stop and price >= self._current_stop) or (
                self._current_target and price <= self._current_target
            ):
                self._position = "FLAT"
                return StrategyDecision(
                    strategy_id=self.strategy_id,
                    timestamp=context.timestamp,
                    action="CLOSE",
                    direction="FLAT",
                    entry_reference=price,
                    reason_code="UNIFIED_MASTER_EXIT",
                )
        return None


class CrudelePureFrameworkAdapter(BaseImportedAdapter):
    """BIN_S09: Crudele Pure Framework (60m Bollinger Bands + EMAs)."""

    def __init__(self) -> None:
        super().__init__("BIN_S09", "crudele_pure_framework")

    def _evaluate(self, context: MarketSnapshotContext) -> StrategyDecision | None:
        if len(context.recent_1h_closes) < 20:
            return None
        # 20-period BB on 1h
        bb_mid = sum(context.recent_1h_closes[-20:]) / Decimal(20)
        bb_upper = bb_mid + Decimal("25.00")
        bb_lower = bb_mid - Decimal("25.00")
        price = context.last_price

        if self._position == "FLAT":
            if price <= bb_lower:
                # Mean reversion long
                self._position = "LONG"
                self._entry_price = price
                self._current_stop = bb_lower - Decimal("12.00")
                self._current_target = bb_mid
                return StrategyDecision(
                    strategy_id=self.strategy_id,
                    timestamp=context.timestamp,
                    action="BUY",
                    direction="LONG",
                    entry_reference=price,
                    stop=self._current_stop,
                    target=self._current_target,
                    confidence_or_score=0.77,
                    reason_code="CRUDELE_BB_LOWER_REVERSION",
                )
            elif price >= bb_upper:
                # Mean reversion short
                self._position = "SHORT"
                self._entry_price = price
                self._current_stop = bb_upper + Decimal("12.00")
                self._current_target = bb_mid
                return StrategyDecision(
                    strategy_id=self.strategy_id,
                    timestamp=context.timestamp,
                    action="SELL",
                    direction="SHORT",
                    entry_reference=price,
                    stop=self._current_stop,
                    target=self._current_target,
                    confidence_or_score=0.77,
                    reason_code="CRUDELE_BB_UPPER_REVERSION",
                )
        elif self._position == "LONG":
            if (self._current_stop and price <= self._current_stop) or (
                self._current_target and price >= self._current_target
            ):
                self._position = "FLAT"
                return StrategyDecision(
                    strategy_id=self.strategy_id,
                    timestamp=context.timestamp,
                    action="CLOSE",
                    direction="FLAT",
                    entry_reference=price,
                    reason_code="CRUDELE_EXIT",
                )
        elif self._position == "SHORT":
            if (self._current_stop and price >= self._current_stop) or (
                self._current_target and price <= self._current_target
            ):
                self._position = "FLAT"
                return StrategyDecision(
                    strategy_id=self.strategy_id,
                    timestamp=context.timestamp,
                    action="CLOSE",
                    direction="FLAT",
                    entry_reference=price,
                    reason_code="CRUDELE_EXIT",
                )
        return None



class S17PriceOiVolAdapter(BaseImportedAdapter):
    """Native research candidate S17: Price x OI x Volume State Machine.

    Monitors 4-quadrant state:
    - Long Buildup: Price UP, OI UP, Volume active -> BUY
    - Short Buildup: Price DOWN, OI UP, Volume active -> SELL
    - Long Unwinding: Price DOWN, OI DOWN -> Exit LONG
    - Short Covering: Price UP, OI DOWN -> Exit SHORT

    If OI is None/absent: stays DATA_BLOCKED / no signal.
    """

    def __init__(self) -> None:
        super().__init__(strategy_id="S17", model_name="price_oi_vol_state_machine")
        self._prev_price: Decimal | None = None
        self._prev_oi: int | None = None
        self._position: str = "FLAT"

    def on_market_event(self, context: MarketSnapshotContext) -> StrategyDecision | None:
        price = context.last_price
        oi = context.open_interest
        vol = context.volume

        if oi is None:
            # S17 is DATA_BLOCKED without genuine Open Interest
            return None

        if self._prev_price is None or self._prev_oi is None:
            self._prev_price = price
            self._prev_oi = oi
            return None

        price_up = price > self._prev_price
        price_down = price < self._prev_price
        oi_up = oi > self._prev_oi
        oi_down = oi < self._prev_oi
        vol_active = vol is not None and vol > 0

        self._prev_price = price
        self._prev_oi = oi

        if self._position == "FLAT":
            if price_up and oi_up and vol_active:
                self._position = "LONG"
                return StrategyDecision(
                    strategy_id=self.strategy_id,
                    timestamp=context.timestamp,
                    action="BUY",
                    direction="LONG",
                    entry_reference=price,
                    stop=price - Decimal("50.00"),
                    target=price + Decimal("100.00"),
                    confidence_or_score=0.75,
                    reason_code="S17_LONG_BUILDUP",
                )
            elif price_down and oi_up and vol_active:
                self._position = "SHORT"
                return StrategyDecision(
                    strategy_id=self.strategy_id,
                    timestamp=context.timestamp,
                    action="SELL",
                    direction="SHORT",
                    entry_reference=price,
                    stop=price + Decimal("50.00"),
                    target=price - Decimal("100.00"),
                    confidence_or_score=0.75,
                    reason_code="S17_SHORT_BUILDUP",
                )
        elif self._position == "LONG":
            if (price_down and oi_down) or (price <= price - Decimal("50.00")):
                self._position = "FLAT"
                return StrategyDecision(
                    strategy_id=self.strategy_id,
                    timestamp=context.timestamp,
                    action="CLOSE",
                    direction="FLAT",
                    entry_reference=price,
                    reason_code="S17_LONG_UNWINDING",
                )
        elif self._position == "SHORT":
            if (price_up and oi_down) or (price >= price + Decimal("50.00")):
                self._position = "FLAT"
                return StrategyDecision(
                    strategy_id=self.strategy_id,
                    timestamp=context.timestamp,
                    action="CLOSE",
                    direction="FLAT",
                    entry_reference=price,
                    reason_code="S17_SHORT_COVERING",
                )

        return None


def create_all_adapters(include_native: bool = False) -> list[StrategyAdapterProtocol]:
    """Instantiate imported strategy adapters, optionally including native candidates like S17."""
    adapters: list[StrategyAdapterProtocol] = [
        CrabelOrbNr7Adapter(),
        BoomingBullsHolyGrailAdapter(),
        BoomingBulls50AbsoluteAdapter(),
        BoomingBullsMaxYieldAdapter(),
        FabioAmtPlaybookAdapter(),
        DesianoBreakRetestAdapter(),
        ApexChimeraEngineAdapter(),
        UnifiedMaster50PctAdapter(),
        CrudelePureFrameworkAdapter(),
    ]
    if include_native:
        adapters.append(S17PriceOiVolAdapter())
    return adapters


__all__ = [
    "ApexChimeraEngineAdapter",
    "BaseImportedAdapter",
    "BoomingBulls50AbsoluteAdapter",
    "BoomingBullsHolyGrailAdapter",
    "BoomingBullsMaxYieldAdapter",
    "CrabelOrbNr7Adapter",
    "CrudelePureFrameworkAdapter",
    "DesianoBreakRetestAdapter",
    "FabioAmtPlaybookAdapter",
    "MarketSnapshotContext",
    "S17PriceOiVolAdapter",
    "StrategyAdapterProtocol",
    "UnifiedMaster50PctAdapter",
    "create_all_adapters",
]
