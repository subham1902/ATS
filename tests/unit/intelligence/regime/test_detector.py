from __future__ import annotations

from datetime import timedelta

import pytest
from ats.contracts.domain.hashing import compute_payload_hash
from ats.contracts.domain.types import DataQualityState
from ats.contracts.intelligence.types import (
    LiquidityState,
    RegimeDirection,
    RegimeStructure,
    VolatilityState,
)
from ats.intelligence.regime import RegimeInputError, detect_regime

from .helpers import bundle, configuration, context


@pytest.mark.parametrize(
    ("roc", "position", "direction", "structure"),
    [
        (0.015, 0.9, RegimeDirection.UP, RegimeStructure.BREAKOUT),
        (-0.015, 0.1, RegimeDirection.DOWN, RegimeStructure.BREAKOUT),
        (0.015, 0.5, RegimeDirection.UP, RegimeStructure.TREND),
        (-0.015, 0.5, RegimeDirection.DOWN, RegimeStructure.TREND),
        (0.0, 0.5, RegimeDirection.FLAT, RegimeStructure.RANGE),
        (0.005, 0.5, RegimeDirection.UP, RegimeStructure.TRANSITION),
    ],
)
def test_direction_and_structure_matrix(
    roc: float,
    position: float,
    direction: RegimeDirection,
    structure: RegimeStructure,
) -> None:
    current = bundle(1, roc=roc, position=position)
    evidence = detect_regime(
        market_context=context(current),
        feature_history=(current,),
        configuration=configuration(),
    )
    assert evidence.direction is direction
    assert evidence.structure is structure
    assert evidence.payload_hash == compute_payload_hash(evidence)


@pytest.mark.parametrize(
    ("prior", "current_value", "expected"),
    [
        (0.01, 0.02, VolatilityState.EXPANDING),
        (0.02, 0.005, VolatilityState.CONTRACTING),
        (0.01, 0.001, VolatilityState.CONTRACTING),
        (0.01, 0.03, VolatilityState.EXPANDING),
        (0.01, 0.01, VolatilityState.NORMAL),
    ],
)
def test_volatility_matrix(prior: float, current_value: float, expected: VolatilityState) -> None:
    previous = bundle(1, volatility=prior)
    current = bundle(2, volatility=current_value)
    evidence = detect_regime(
        market_context=context(current),
        feature_history=(previous, current),
        configuration=configuration(),
    )
    assert evidence.volatility is expected


def test_absolute_low_and_high_volatility_without_prior() -> None:
    low = bundle(1, volatility=0.001)
    high = bundle(2, volatility=0.03)
    assert (
        detect_regime(
            market_context=context(low), feature_history=(low,), configuration=configuration()
        ).volatility
        is VolatilityState.LOW
    )
    assert (
        detect_regime(
            market_context=context(high), feature_history=(high,), configuration=configuration()
        ).volatility
        is VolatilityState.HIGH
    )


def test_change_and_familiarity_are_bounded_non_probability_scores() -> None:
    previous = bundle(1, roc=-0.02, volatility=0.001)
    current = bundle(2, roc=0.02, volatility=0.03)
    evidence = detect_regime(
        market_context=context(current),
        feature_history=(previous, current),
        configuration=configuration(),
    )
    assert 0.0 <= evidence.change_score <= 1.0
    assert evidence.change_score == 1.0
    assert evidence.regime_familiarity == 0.2


@pytest.mark.parametrize(
    ("quality", "flags", "features"),
    [
        (DataQualityState.UNKNOWN, (), None),
        (DataQualityState.INVALID, (), None),
        (DataQualityState.GOOD, ("INSUFFICIENT_WARMUP",), None),
        (DataQualityState.GOOD, (), {"roc_3_fraction": 0.1}),
    ],
)
def test_unknown_quality_never_becomes_known_regime(
    quality: DataQualityState,
    flags: tuple[str, ...],
    features: dict[str, float] | None,
) -> None:
    current = bundle(1, quality_flags=flags, features=features)
    evidence = detect_regime(
        market_context=context(current, quality=quality),
        feature_history=(current,),
        configuration=configuration(),
    )
    assert evidence.direction is RegimeDirection.UNKNOWN
    assert evidence.structure is RegimeStructure.UNKNOWN
    assert evidence.volatility is VolatilityState.UNKNOWN
    assert evidence.liquidity is LiquidityState.UNKNOWN
    assert evidence.quality_state is DataQualityState.UNKNOWN


def test_unknown_liquidity_is_preserved_and_degrades_quality() -> None:
    current = bundle(1)
    evidence = detect_regime(
        market_context=context(current, liquidity=LiquidityState.UNKNOWN),
        feature_history=(current,),
        configuration=configuration(),
    )
    assert evidence.liquidity is LiquidityState.UNKNOWN
    assert evidence.quality_state is DataQualityState.DEGRADED


@pytest.mark.parametrize(
    "mode", ["empty", "wrong_bundle", "wrong_snapshot", "duplicate", "version"]
)
def test_lineage_failures_rejected(mode: str) -> None:
    previous = bundle(1)
    current = bundle(2)
    ctx = context(current)
    history = (previous, current)
    if mode == "empty":
        history = ()
    elif mode == "wrong_bundle":
        ctx = ctx.model_copy(update={"feature_bundle_id": previous.feature_bundle_id})
    elif mode == "wrong_snapshot":
        ctx = ctx.model_copy(update={"snapshot_id": previous.snapshot_id})
    elif mode == "duplicate":
        history = (current, current)
    elif mode == "version":
        previous = previous.model_copy(update={"feature_version": "2.0.0"})
        history = (previous, current)
    with pytest.raises(RegimeInputError):
        detect_regime(
            market_context=ctx,
            feature_history=history,
            configuration=configuration(),
        )


def test_future_and_out_of_order_feature_evidence_rejected() -> None:
    previous = bundle(1)
    current = bundle(2)
    ctx = context(current)
    future = previous.model_copy(update={"computed_at": ctx.as_of_time + timedelta(seconds=1)})
    with pytest.raises(RegimeInputError):
        detect_regime(
            market_context=ctx,
            feature_history=(current, future),
            configuration=configuration(),
        )
    with pytest.raises(RegimeInputError):
        detect_regime(
            market_context=ctx,
            feature_history=(current, previous),
            configuration=configuration(),
        )


def test_configuration_rejects_unsafe_threshold_shapes() -> None:
    config = configuration()
    for update in (
        {"breakout_low": 0.9},
        {"low_volatility_threshold": 0.03},
        {"expansion_ratio": 1.0},
        {"contraction_ratio": 1.0},
    ):
        with pytest.raises(ValueError):
            type(config)(**(config.model_dump() | update))
