from __future__ import annotations

import pytest
from ats.intelligence.calibration import CalibrationInputError, calibrate_outcome_distribution

from tests.unit.intelligence.calibration.helpers import (
    calibration_config,
    ensemble,
    observation,
    observations,
)
from tests.unit.intelligence.ensemble.helpers import context


def run(items=None, *, config=None):
    resolved_items = observations() if items is None else items
    return calibrate_outcome_distribution(
        ensemble=ensemble(),
        market_context=context(),
        target_outcome_code="ABOVE",
        observations=resolved_items,
        configuration=config or calibration_config(),
        regime_evidence=None,
    )


def test_repeated_input_is_byte_deterministic() -> None:
    first = run()
    second = run()
    assert first.model_dump_json() == second.model_dump_json()


def test_set_like_input_order_does_not_change_result() -> None:
    items = observations()
    assert run(items).model_dump_json() == run(tuple(reversed(items))).model_dump_json()


@pytest.mark.parametrize("probability", ["0", "0.0001", "0.5", "0.9999", "1"])
def test_probability_boundaries_remain_finite(probability: str) -> None:
    items = tuple(
        observation(index, index % 2 == 0, probability=probability)
        for index in range(1, 4)
    )
    config = calibration_config().model_copy(update={"bin_count": 1})
    assert run(items, config=config).distribution is not None


def test_future_suffix_cannot_enter_calibration_window() -> None:
    future = observation(10, True, minutes_before=-5)
    with pytest.raises(CalibrationInputError, match="future"):
        run(observations() + (future,))


def test_out_of_bin_history_does_not_fabricate_support() -> None:
    items = tuple(observation(index, True, probability="0.2") for index in range(1, 8))
    result = run(items)
    assert result.distribution is None
    assert result.support_count == 0
