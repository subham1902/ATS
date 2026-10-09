"""Frozen clean-room lineage allocation. Never reorder or reuse these numbers."""

from pathlib import Path

from ats.strategies.operating_system import StrategyStore

DEFINITIONS = (
    "atr_expansion",
    "close_location",
    "donchian",
    "fade_extreme",
    "gap_fill",
    "hurst_regime",
    "moment_skew",
    "oi_volume",
    "regime_gate",
    "session_seasonality",
    "squeeze",
    "tick_velocity",
    "tsmom",
    "volume_divergence",
    "vwap_trend",
    "zscore",
    "S5_ORB_XAUUSD",
    "gold_triple_s1_intraday_retest",
    "gold_triple_s2_intraday_retest",
    "gold_triple_s3_h4_close_retest",
)


def bootstrap_store(path: Path) -> StrategyStore:
    store = StrategyStore(path)
    # A clean-room store starts empty. An existing unknown mapping fails closed
    # instead of silently assigning different lineages to the same IDs.
    for number, definition in enumerate(DEFINITIONS, 1):
        record = store.register(definition, definition.replace("_", " "))
        if record.strategy_id != f"XAU-{number:03d}":
            raise ValueError("CANONICAL_STRATEGY_LINEAGE_MISMATCH")
    return store
