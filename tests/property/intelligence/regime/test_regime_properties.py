from __future__ import annotations

from datetime import timedelta

import pytest
from ats.intelligence.regime import RegimeInputError, detect_regime

from tests.unit.intelligence.regime.helpers import bundle, configuration, context


def test_identical_inputs_produce_identical_evidence() -> None:
    history = (bundle(1, roc=0.01), bundle(2, roc=0.02))
    first = detect_regime(
        market_context=context(history[-1]),
        feature_history=history,
        configuration=configuration(),
    )
    second = detect_regime(
        market_context=context(history[-1]),
        feature_history=history,
        configuration=configuration(),
    )
    assert first == second
    assert first.model_dump_json() == second.model_dump_json()


def test_future_suffix_cannot_change_cutoff_evidence() -> None:
    history = (bundle(1), bundle(2, roc=0.02))
    baseline = detect_regime(
        market_context=context(history[-1]),
        feature_history=history,
        configuration=configuration(),
    )
    assert baseline.direction.value == "UP"
    future = bundle(3, roc=-0.5).model_copy(
        update={"computed_at": history[-1].computed_at + timedelta(minutes=5)}
    )
    with pytest.raises(RegimeInputError):
        detect_regime(
            market_context=context(history[-1]),
            feature_history=history + (future,),
            configuration=configuration(),
        )


def test_reason_order_is_deterministic() -> None:
    current = bundle(1, roc=0.02, position=0.9)
    evidence = detect_regime(
        market_context=context(current),
        feature_history=(current,),
        configuration=configuration(),
    )
    assert evidence.reason_codes == (
        "DIRECTION_UP",
        "STRUCTURE_BREAKOUT",
        "VOLATILITY_NORMAL",
        "LIQUIDITY_NORMAL",
    )
