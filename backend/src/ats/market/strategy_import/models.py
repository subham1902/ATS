"""ATS-BIN-01 Normalized Strategy Import Contracts.

All models derive from ATSBaseModel with strict frozen schemas.
Imported strategies strictly have authority = RESEARCH_ONLY and are forbidden
from executing real or paper broker orders.
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import Literal

from ats.contracts.common import ATSBaseModel, UTCDateTime
from ats.contracts.domain.types import NonEmptyStr


class StrategyCompatibilityState(StrEnum):
    LIVE_COMPATIBLE = "LIVE_COMPATIBLE"
    LIVE_COMPATIBLE_WITH_LIMITATIONS = "LIVE_COMPATIBLE_WITH_LIMITATIONS"
    HISTORICAL_ONLY = "HISTORICAL_ONLY"
    DATA_BLOCKED = "DATA_BLOCKED"
    RUNTIME_BLOCKED = "RUNTIME_BLOCKED"
    QUARANTINED = "QUARANTINED"


class StrategyStatus(StrEnum):
    IMPORTED = "IMPORTED"
    QUARANTINED = "QUARANTINED"
    DATA_BLOCKED = "DATA_BLOCKED"
    RUNTIME_BLOCKED = "RUNTIME_BLOCKED"
    SHADOW_READY = "SHADOW_READY"
    SHADOW_RUNNING = "SHADOW_RUNNING"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    PROMISING_SHADOW = "PROMISING_SHADOW"
    REJECTED_SHADOW = "REJECTED_SHADOW"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class StrategyDecision(ATSBaseModel):
    """Normalized output from an imported strategy adapter on one market tick."""

    strategy_id: NonEmptyStr
    timestamp: UTCDateTime
    action: Literal["BUY", "SELL", "HOLD", "CLOSE"]
    direction: Literal["LONG", "SHORT", "FLAT"]
    entry_reference: Decimal | None = None
    stop: Decimal | None = None
    target: Decimal | None = None
    confidence_or_score: float = 0.0
    reason_code: str = "NO_SIGNAL"
    metadata: dict[str, str] = {}


class ImportedStrategyMetadata(ATSBaseModel):
    """Normalized ATS definition for an imported strategy."""

    strategy_id: NonEmptyStr
    model_name: NonEmptyStr
    source_file: NonEmptyStr
    source_hash: NonEmptyStr
    source_format: NonEmptyStr
    version: NonEmptyStr = "1.0.0"
    authority: Literal["RESEARCH_ONLY"] = "RESEARCH_ONLY"
    instrument_scope: tuple[str, ...] = ("MCX_FO|GOLDM", "MCX_FO|GOLD")
    timeframes: tuple[str, ...]
    required_features: tuple[str, ...]
    required_data_fields: tuple[str, ...]
    entry_policy: str
    exit_policy: str
    risk_policy_reference: str
    state_requirements: tuple[str, ...]
    runtime_type: str = "ATS_SHADOW_ADAPTER"
    compatibility_state: StrategyCompatibilityState
    status: StrategyStatus = StrategyStatus.IMPORTED
    blockers: tuple[str, ...] = ()


class ShadowMetrics(ATSBaseModel):
    """Live shadow tournament telemetry for one strategy candidate."""

    strategy_id: NonEmptyStr
    model_name: NonEmptyStr
    is_native: bool = False
    signals_generated: int = 0
    valid_signals: int = 0
    invalid_signals: int = 0
    long_count: int = 0
    short_count: int = 0
    open_trajectories: int = 0
    resolved_trajectories: int = 0
    support_count: int = 0
    support_target: int = 20
    wins: int = 0
    losses: int = 0
    gross_pnl: Decimal = Decimal("0.00")
    costs: Decimal = Decimal("0.00")
    net_pnl: Decimal = Decimal("0.00")
    cost_stress_base: Decimal = Decimal("0.00")
    cost_stress_1_5x: Decimal = Decimal("0.00")
    cost_stress_2_0x: Decimal = Decimal("0.00")
    win_rate: float = 0.0
    profit_factor: float = 0.0
    expectancy: Decimal = Decimal("0.00")
    max_drawdown: Decimal = Decimal("0.00")
    mae: Decimal = Decimal("0.00")
    mfe: Decimal = Decimal("0.00")
    average_r: float = 0.0
    holding_time_seconds: float = 0.0
    latency_ms: float = 0.0
    regime: str = "UNKNOWN"
    regime_classification: str = "INSUFFICIENT_EVIDENCE"
    data_freshness_sec: float = 0.0
    jev_state: str = "RESEARCH_ONLY"
    jev_incremental_benefit: bool = False
    sample_status: Literal["INSUFFICIENT_EVIDENCE", "VALIDATED"] = "INSUFFICIENT_EVIDENCE"
    status: StrategyStatus = StrategyStatus.SHADOW_READY


__all__ = [
    "ImportedStrategyMetadata",
    "ShadowMetrics",
    "StrategyCompatibilityState",
    "StrategyDecision",
    "StrategyStatus",
]
