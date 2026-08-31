from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from ats.contracts.domain import FeatureBundle, compute_payload_hash
from ats.contracts.domain.types import DataQualityState
from ats.market.features import FeatureInputError, compute_feature_bundle

from .helpers import four_bars, snapshot


def test_first_bar_emits_only_supported_candle_features() -> None:
    bar = snapshot(1)
    bundle = compute_feature_bundle((bar,), cutoff_sequence=1)
    assert isinstance(bundle, FeatureBundle)
    assert bundle.snapshot_id == bar.snapshot_id
    assert tuple(bundle.features) == (
        "candle_body",
        "candle_range",
        "upper_wick",
        "lower_wick",
    )
    assert bundle.features == {
        "candle_body": 1.0,
        "candle_range": 3.0,
        "upper_wick": 1.0,
        "lower_wick": 1.0,
    }
    assert bundle.quality_flags == ("INSUFFICIENT_WARMUP",)
    assert bundle.computed_at == bar.received_at


def test_returns_use_exact_previous_close_semantics() -> None:
    bars = four_bars()
    bundle = compute_feature_bundle(bars, cutoff_sequence=2)
    assert bundle.features["simple_return"] == float(Decimal(103) / Decimal(101) - 1)
    assert bundle.features["log_return"] == pytest.approx(0.019608471388376337)


@pytest.mark.parametrize(
    ("bars", "message"),
    [
        (
            (snapshot(1), snapshot(2).model_copy(update={"instrument_id": "TCS"})),
            "mixed instruments",
        ),
        (
            (snapshot(1), snapshot(2).model_copy(update={"timeframe": "15m"})),
            "mixed timeframes",
        ),
        ((snapshot(1), snapshot(1), snapshot(2)), "sequences"),
        ((snapshot(1), snapshot(3)), "sequences"),
    ],
)
def test_invalid_histories_fail_closed(bars: tuple[object, ...], message: str) -> None:
    with pytest.raises(FeatureInputError, match=message):
        compute_feature_bundle(bars, cutoff_sequence=bars[-1].sequence)  # type: ignore[attr-defined,arg-type]


def test_out_of_order_timestamp_is_rejected() -> None:
    first, second = snapshot(1), snapshot(2)
    moved = second.model_copy(update={"bar_timestamp": first.bar_timestamp - timedelta(minutes=5)})
    moved = moved.model_copy(update={"payload_hash": compute_payload_hash(moved)})
    with pytest.raises(FeatureInputError, match="timestamps"):
        compute_feature_bundle((first, moved), cutoff_sequence=2)


def test_bad_quality_and_payload_hash_are_rejected() -> None:
    bad_quality = snapshot(1, quality_state=DataQualityState.DEGRADED)
    with pytest.raises(FeatureInputError, match="GOOD"):
        compute_feature_bundle((bad_quality,), cutoff_sequence=1)
    with pytest.raises(FeatureInputError, match="payload hash"):
        compute_feature_bundle(
            (snapshot(1).model_copy(update={"payload_hash": "f" * 64}),),
            cutoff_sequence=1,
        )


def test_cutoff_must_be_present_and_strict_positive_int() -> None:
    bars = four_bars()
    for invalid in (0, -1, True):
        with pytest.raises(FeatureInputError, match="positive integer"):
            compute_feature_bundle(bars, cutoff_sequence=invalid)  # type: ignore[arg-type]
    with pytest.raises(FeatureInputError, match="not present"):
        compute_feature_bundle(bars, cutoff_sequence=9)
