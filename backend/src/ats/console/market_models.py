"""Read models for the market-data surface.

Every market field is optional. An absent provider value stays ``None`` and the
enclosing view carries an explicit :class:`MarketDataState` plus reason codes,
so the console can render "unknown" honestly instead of a plausible number.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from ats.contracts.common import ATSBaseModel, FiniteDecimal, UTCDateTime
from ats.contracts.enums import ATSStringEnum


class MarketDataState(ATSStringEnum):
    """Truthful availability of a market read model."""

    LIVE = "LIVE"
    STALE = "STALE"
    NO_FEED = "NO_FEED"
    UNKNOWN = "UNKNOWN"


class AuthorityClass(ATSStringEnum):
    """Execution and governance authority tier."""

    CANONICAL_MARKET_DATA = "CANONICAL_MARKET_DATA"
    REFERENCE_FEATURE = "REFERENCE_FEATURE"
    INTELLIGENCE_ONLY = "INTELLIGENCE_ONLY"
    DISPLAY_ONLY = "DISPLAY_ONLY"
    RESEARCH_ONLY = "RESEARCH_ONLY"


class FreshnessState(ATSStringEnum):
    """Formal freshness semantics."""

    STREAMING = "STREAMING"
    LIVE = "LIVE"
    NEAR_REAL_TIME = "NEAR_REAL_TIME"
    DELAYED = "DELAYED"
    DAILY = "DAILY"
    STALE = "STALE"
    OFFLINE = "OFFLINE"
    UNKNOWN = "UNKNOWN"


class MarketInterval(ATSStringEnum):
    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    H1 = "1h"
    D1 = "1d"


class CandleView(ATSBaseModel):
    """One aggregated bar; in-progress bars are explicitly not closed."""

    bar_start: UTCDateTime
    bar_close: UTCDateTime
    open: FiniteDecimal | None = None
    high: FiniteDecimal | None = None
    low: FiniteDecimal | None = None
    close: FiniteDecimal | None = None
    volume: int | None = None
    open_interest: int | None = None
    tick_count: int
    is_closed: bool


class CandleSeriesView(ATSBaseModel):
    """Bar series plus the provenance needed to interpret it correctly."""

    instrument_key: str
    contract: str | None = None
    interval: MarketInterval
    state: MarketDataState
    bar_alignment_offset_minutes: int
    bar_alignment_note: str
    source: str | None = None
    authority_class: str
    candles: tuple[CandleView, ...]
    reason_codes: tuple[str, ...]


class MarketQuoteView(ATSBaseModel):
    """Last accepted observation for one instrument key."""

    instrument_key: str
    state: MarketDataState
    contract: str | None = None
    last_price: FiniteDecimal | None = None
    bid_price: FiniteDecimal | None = None
    ask_price: FiniteDecimal | None = None
    bid_quantity: int | None = None
    ask_quantity: int | None = None
    spread: FiniteDecimal | None = None
    volume: int | None = None
    open_interest: int | None = None
    open_interest_change: int | None = None
    exchange_timestamp: UTCDateTime | None = None
    received_at: UTCDateTime | None = None
    age_ms: int | None = None
    source: str | None = None
    authority_class: str
    reason_codes: tuple[str, ...]


class FeedHealthView(ATSBaseModel):
    """Distribution-layer health; counters are real, never synthesised."""

    state: MarketDataState
    attached: bool
    source: str | None = None
    authority_class: str
    instruments: tuple[str, ...]
    last_update_at: UTCDateTime | None = None
    last_update_age_ms: int | None = None
    stale_after_ms: int
    accepted_updates: int
    dropped_duplicate: int
    dropped_out_of_order: int
    dropped_stale: int
    subscriber_count: int
    reason_codes: tuple[str, ...]
    provider_state: str | None = None
    reconnect_count: int | None = None
    events_received: int | None = None
    decode_errors: int | None = None
    quote_age_ms: int | None = None
    trade_age_ms: int | None = None
    depth_age_ms: int | None = None
    oi_age_ms: int | None = None
    stream_clients: int | None = None


class StrategyPredictionView(ATSBaseModel):
    """Dynamic strategy prediction data updated on every tick."""

    strategy_id: str
    probability_long: float
    probability_short: float
    dynamic_sl: FiniteDecimal
    dynamic_tp: FiniteDecimal
    confidence_score: float

class MarketStreamFrame(ATSBaseModel):
    """One SSE frame on the market channel."""

    frame_kind: Literal["TICK", "FEED_STATE", "PREDICTION"]
    quote: MarketQuoteView | None = None
    health: FeedHealthView | None = None
    prediction: StrategyPredictionView | None = None


class MarketSnapshotView(ATSBaseModel):
    """Unified read-side snapshot across quote, health, and session."""

    instrument_key: str
    state: MarketDataState
    contract: str | None = None
    last_price: FiniteDecimal | None = None
    bid_price: FiniteDecimal | None = None
    ask_price: FiniteDecimal | None = None
    spread: FiniteDecimal | None = None
    volume: int | None = None
    open_interest: int | None = None
    open_interest_change: int | None = None
    market_session: str | None = None
    provider: str | None = None
    source: str | None = None
    authority_class: str
    exchange_timestamp: UTCDateTime | None = None
    received_at: UTCDateTime | None = None
    freshness_ms: int | None = None
    sequence: int | None = None
    connection_state: MarketDataState
    reason_codes: tuple[str, ...] = ()


class TradeView(ATSBaseModel):
    """Normalized executed trade tick."""

    trade_id: str
    instrument_key: str
    price: FiniteDecimal
    quantity: int
    executed_at: UTCDateTime
    source: str
    authority_class: AuthorityClass = AuthorityClass.CANONICAL_MARKET_DATA


class OrderBookLevel(ATSBaseModel):
    """One depth level in the order book."""

    price: FiniteDecimal
    quantity: int
    orders_count: int | None = None


class OrderBookView(ATSBaseModel):
    """Normalized market depth."""

    instrument_key: str
    bids: tuple[OrderBookLevel, ...]
    asks: tuple[OrderBookLevel, ...]
    updated_at: UTCDateTime
    authority_class: AuthorityClass = AuthorityClass.CANONICAL_MARKET_DATA
    freshness: FreshnessState = FreshnessState.STREAMING


class NewsItemView(ATSBaseModel):
    """Normalized intelligence news item."""

    id: str
    headline: str
    summary: str
    source: str
    published_at: UTCDateTime
    relevant_instruments: tuple[str, ...]
    sentiment: Literal["BULLISH", "BEARISH", "NEUTRAL"]
    authority_class: AuthorityClass = AuthorityClass.INTELLIGENCE_ONLY


class MacroPointView(ATSBaseModel):
    """Normalized macroeconomic indicator observation."""

    indicator_key: str
    name: str
    value: FiniteDecimal
    unit: str
    observed_at: UTCDateTime
    source: str
    authority_class: AuthorityClass = AuthorityClass.REFERENCE_FEATURE
    freshness: FreshnessState = FreshnessState.DAILY


class EconomicEventView(ATSBaseModel):
    """Normalized scheduled economic calendar event."""

    event_id: str
    title: str
    country: str
    impact: Literal["LOW", "MEDIUM", "HIGH"]
    scheduled_at: UTCDateTime
    previous: str | None = None
    forecast: str | None = None
    actual: str | None = None
    authority_class: AuthorityClass = AuthorityClass.INTELLIGENCE_ONLY


class ReferenceIntelligenceItem(ATSBaseModel):
    """Reference market price point (e.g. XAUUSD, DXY, USDINR)."""

    symbol: str
    name: str
    price: FiniteDecimal
    change_24h_pct: float
    high_24h: FiniteDecimal | None = None
    low_24h: FiniteDecimal | None = None
    source: str
    authority_class: AuthorityClass = AuthorityClass.REFERENCE_FEATURE
    freshness: FreshnessState = FreshnessState.NEAR_REAL_TIME
    age_ms: int | None = None


class ReferenceIntelligenceView(ATSBaseModel):
    """Collection of reference macro and commodity items."""

    items: tuple[ReferenceIntelligenceItem, ...]
    macro_indicators: tuple[MacroPointView, ...]
    news: tuple[NewsItemView, ...]
    calendar: tuple[EconomicEventView, ...]
    updated_at: UTCDateTime


class DualSourceComparisonView(ATSBaseModel):
    """Comparison view between Broker Live and Reference/OpenTerminal."""

    instrument_key: str
    broker_price: FiniteDecimal | None = None
    broker_timestamp: UTCDateTime | None = None
    broker_freshness: FreshnessState = FreshnessState.UNKNOWN
    reference_price: FiniteDecimal | None = None
    reference_timestamp: UTCDateTime | None = None
    reference_freshness: FreshnessState = FreshnessState.UNKNOWN
    price_difference: FiniteDecimal | None = None
    difference_pct: float | None = None
    basis_note: str
    diagnosis: str


__all__ = [
    "AuthorityClass",
    "CandleSeriesView",
    "CandleView",
    "DualSourceComparisonView",
    "EconomicEventView",
    "FeedHealthView",
    "FreshnessState",
    "MacroPointView",
    "MarketDataState",
    "MarketInterval",
    "MarketQuoteView",
    "MarketSnapshotView",
    "MarketStreamFrame",
    "NewsItemView",
    "OrderBookLevel",
    "OrderBookView",
    "ReferenceIntelligenceItem",
    "ReferenceIntelligenceView",
    "StrategyPredictionView",
    "TradeView",
]


